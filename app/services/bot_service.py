"""
Bot Service - бизнес-логика управления ботами
"""

import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.orm import selectinload

from app.models.bot import Bot, BotStatus, BotSubscriber
from app.models.user import User
from app.schemas.bot import BotCreate, BotUpdate, BotConfigUpdate
from app.core.exceptions import BotNotFoundError, ValidationError, BotLimitReachedError
from app.utils.telegram import verify_bot_token
from app.services.base import BaseService

logger = logging.getLogger(__name__)


class BotService(BaseService):
    """Service for bot management"""
    
    async def create_bot(
        self, 
        db: AsyncSession, 
        bot_data: BotCreate, 
        owner_id: int
    ) -> Bot:
        """Create new bot"""
        try:
            # Check bot limit
            await self._check_bot_limit(db, owner_id)
            
            # Verify bot token
            bot_info = await verify_bot_token(bot_data.bot_token)
            if not bot_info:
                raise ValidationError("Invalid bot token")
            
            # Check if bot already exists
            existing_bot = await self._get_bot_by_token(db, bot_data.bot_token)
            if existing_bot:
                raise ValidationError("Bot already exists")
            
            # Create bot instance
            bot = Bot(
                owner_id=owner_id,
                bot_token=bot_data.bot_token,
                bot_username=bot_info['username'],
                bot_display_name=bot_data.bot_display_name or bot_info['first_name'],
                channel_id=bot_data.channel_id,
                channel_username=bot_data.channel_username,
                auto_approve_requests=bot_data.auto_approve_requests,
                welcome_message_enabled=bot_data.welcome_message_enabled,
                farewell_message_enabled=bot_data.farewell_message_enabled,
                utm_tracking_enabled=bot_data.utm_tracking_enabled,
                welcome_message=bot_data.welcome_message,
                farewell_message=bot_data.farewell_message,
                auto_approve_message=bot_data.auto_approve_message,
                status=BotStatus.CREATING.value
            )
            
            db.add(bot)
            await db.flush()
            await db.refresh(bot)
            
            logger.info(f"Created bot {bot.id} for user {owner_id}")
            return bot
            
        except Exception as e:
            logger.error(f"Error creating bot: {e}")
            raise
    
    async def get_bot(self, db: AsyncSession, bot_id: int, owner_id: Optional[int] = None) -> Bot:
        """Get bot by ID"""
        query = select(Bot).where(Bot.id == bot_id)
        
        if owner_id:
            query = query.where(Bot.owner_id == owner_id)
        
        result = await db.execute(query)
        bot = result.scalar_one_or_none()
        
        if not bot:
            raise BotNotFoundError("Bot not found")
        
        return bot
    
    async def get_user_bots(
        self, 
        db: AsyncSession, 
        owner_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Bot]:
        """Get all bots for user"""
        query = (
            select(Bot)
            .where(Bot.owner_id == owner_id)
            .order_by(Bot.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def update_bot(
        self, 
        db: AsyncSession, 
        bot_id: int, 
        bot_data: BotUpdate, 
        owner_id: Optional[int] = None
    ) -> Bot:
        """Update bot"""
        bot = await self.get_bot(db, bot_id, owner_id)
        
        update_data = bot_data.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(bot, field, value)
        
        await db.flush()
        await db.refresh(bot)
        
        logger.info(f"Updated bot {bot_id}")
        return bot
    
    async def update_bot_config(
        self, 
        db: AsyncSession, 
        bot_id: int, 
        config_data: BotConfigUpdate, 
        owner_id: Optional[int] = None
    ) -> Bot:
        """Update bot configuration"""
        bot = await self.get_bot(db, bot_id, owner_id)
        
        update_data = config_data.dict(exclude_unset=True)
        
        # Update simple fields
        simple_fields = [
            'welcome_message', 'farewell_message', 'auto_approve_message',
            'auto_approve_requests', 'welcome_message_enabled', 
            'farewell_message_enabled', 'utm_tracking_enabled'
        ]
        
        for field in simple_fields:
            if field in update_data:
                setattr(bot, field, update_data[field])
        
        # Update custom config
        if 'custom_config' in update_data:
            if not bot.config:
                bot.config = {}
            bot.config.update(update_data['custom_config'])
        
        await db.flush()
        await db.refresh(bot)
        
        logger.info(f"Updated bot {bot_id} configuration")
        return bot
    
    async def delete_bot(
        self, 
        db: AsyncSession, 
        bot_id: int, 
        owner_id: Optional[int] = None
    ) -> bool:
        """Delete bot"""
        bot = await self.get_bot(db, bot_id, owner_id)
        
        # Soft delete - mark as deleted
        bot.status = BotStatus.DELETED.value
        
        await db.flush()
        
        logger.info(f"Deleted bot {bot_id}")
        return True
    
    async def update_bot_status(
        self, 
        db: AsyncSession, 
        bot_id: int, 
        status: BotStatus, 
        error_message: Optional[str] = None
    ) -> Bot:
        """Update bot status"""
        query = (
            update(Bot)
            .where(Bot.id == bot_id)
            .values(
                status=status.value,
                error_message=error_message,
                last_ping_at=func.now()
            )
        )
        
        await db.execute(query)
        
        # Get updated bot
        bot = await self.get_bot(db, bot_id)
        
        logger.info(f"Updated bot {bot_id} status to {status.value}")
        return bot
    
    async def get_active_bots(self, db: AsyncSession) -> List[Bot]:
        """Get all active bots"""
        query = select(Bot).where(Bot.status == BotStatus.ACTIVE.value)
        result = await db.execute(query)
        return result.scalars().all()
    
    async def add_subscriber(
        self, 
        db: AsyncSession, 
        bot_id: int, 
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_campaign: Optional[str] = None,
        utm_medium: Optional[str] = None
    ) -> BotSubscriber:
        """Add subscriber to bot"""
        # Check if subscriber already exists
        existing = await self._get_subscriber(db, bot_id, user_id)
        
        if existing:
            # Update existing subscriber
            existing.is_active = True
            existing.username = username
            existing.first_name = first_name
            existing.last_name = last_name
            if utm_source:
                existing.utm_source = utm_source
            if utm_campaign:
                existing.utm_campaign = utm_campaign
            if utm_medium:
                existing.utm_medium = utm_medium
            existing.last_activity_at = func.now()
            
            await db.flush()
            await db.refresh(existing)
            
            return existing
        
        # Create new subscriber
        subscriber = BotSubscriber(
            bot_id=bot_id,
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            utm_source=utm_source,
            utm_campaign=utm_campaign,
            utm_medium=utm_medium,
            is_active=True
        )
        
        db.add(subscriber)
        await db.flush()
        await db.refresh(subscriber)
        
        # Update bot subscriber count
        await self._update_subscriber_count(db, bot_id)
        
        logger.info(f"Added subscriber {user_id} to bot {bot_id}")
        return subscriber
    
    async def remove_subscriber(
        self, 
        db: AsyncSession, 
        bot_id: int, 
        user_id: int
    ) -> bool:
        """Remove subscriber from bot"""
        subscriber = await self._get_subscriber(db, bot_id, user_id)
        
        if subscriber:
            subscriber.is_active = False
            await db.flush()
            
            # Update bot subscriber count
            await self._update_subscriber_count(db, bot_id)
            
            logger.info(f"Removed subscriber {user_id} from bot {bot_id}")
            return True
        
        return False
    
    async def get_bot_subscribers(
        self, 
        db: AsyncSession, 
        bot_id: int, 
        skip: int = 0, 
        limit: int = 100,
        active_only: bool = True
    ) -> List[BotSubscriber]:
        """Get bot subscribers"""
        query = select(BotSubscriber).where(BotSubscriber.bot_id == bot_id)
        
        if active_only:
            query = query.where(BotSubscriber.is_active == True)
        
        query = query.order_by(BotSubscriber.joined_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def _check_bot_limit(self, db: AsyncSession, owner_id: int):
        """Check if user can create more bots"""
        query = (
            select(func.count(Bot.id))
            .where(
                and_(
                    Bot.owner_id == owner_id,
                    Bot.status != BotStatus.DELETED.value
                )
            )
        )
        
        result = await db.execute(query)
        bot_count = result.scalar()
        
        # Get user to check their limit
        user_query = select(User).where(User.id == owner_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise ValidationError("User not found")
        
        # Check limit based on subscription
        max_bots = 5 if user.is_premium else 2
        
        if bot_count >= max_bots:
            raise BotLimitReachedError(f"Maximum {max_bots} bots allowed")
    
    async def _get_bot_by_token(self, db: AsyncSession, token: str) -> Optional[Bot]:
        """Get bot by token"""
        query = select(Bot).where(Bot.bot_token == token)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_subscriber(self, db: AsyncSession, bot_id: int, user_id: int) -> Optional[BotSubscriber]:
        """Get subscriber"""
        query = select(BotSubscriber).where(
            and_(
                BotSubscriber.bot_id == bot_id,
                BotSubscriber.user_id == user_id
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def _update_subscriber_count(self, db: AsyncSession, bot_id: int):
        """Update bot subscriber count"""
        query = (
            select(func.count(BotSubscriber.id))
            .where(
                and_(
                    BotSubscriber.bot_id == bot_id,
                    BotSubscriber.is_active == True
                )
            )
        )
        
        result = await db.execute(query)
        count = result.scalar()
        
        # Update bot
        update_query = (
            update(Bot)
            .where(Bot.id == bot_id)
            .values(total_subscribers=count)
        )
        
        await db.execute(update_query)
