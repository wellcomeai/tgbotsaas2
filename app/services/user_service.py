"""
User Service - бизнес-логика управления пользователями
"""

import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import datetime, timedelta

from app.models.user import User
from app.models.bot import Bot, BotStatus
from app.schemas.user import UserCreate, UserUpdate, UserStats
from app.services.base import BaseService
from app.core.exceptions import UserNotFoundError, ValidationError
from sqlalchemy import select, and_, func, or_
logger = logging.getLogger(__name__)


class UserService(BaseService):
    """Service for user management"""
    
    async def get_user_by_telegram_id(self, db: AsyncSession, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID"""
        query = select(User).where(User.telegram_id == telegram_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def create_user(self, db: AsyncSession, user_data: UserCreate) -> User:
        """Create new user"""
        try:
            # Check if user already exists
            existing_user = await self.get_user_by_telegram_id(db, user_data.telegram_id)
            if existing_user:
                raise ValidationError("User already exists")
            
            user = User(
                telegram_id=user_data.telegram_id,
                username=user_data.username,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                language_code=user_data.language_code,
                timezone=user_data.timezone,
                is_active=True
            )
            
            db.add(user)
            await db.flush()
            await db.refresh(user)
            
            logger.info(f"Created user {user.id} with telegram_id {user.telegram_id}")
            return user
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise
    
    async def update_user(
        self, 
        db: AsyncSession, 
        user_id: int, 
        user_data: UserUpdate
    ) -> User:
        """Update user"""
        user = await self.get_or_404(db, user_id)
        
        update_data = user_data.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        await db.flush()
        await db.refresh(user)
        
        logger.info(f"Updated user {user_id}")
        return user
    
    async def get_or_create_user(
        self, 
        db: AsyncSession, 
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: str = "ru"
    ) -> User:
        """Get existing user or create new one"""
        user = await self.get_user_by_telegram_id(db, telegram_id)
        
        if user:
            # Update user info if provided
            updated = False
            if username and user.username != username:
                user.username = username
                updated = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated = True
            
            if updated:
                await db.flush()
                await db.refresh(user)
            
            return user
        
        # Create new user
        user_data = UserCreate(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code
        )
        
        return await self.create_user(db, user_data)
    
    async def update_user_activity(self, db: AsyncSession, user_id: int):
        """Update user last activity"""
        user = await self.get_or_404(db, user_id)
        user.updated_at = datetime.utcnow()
        await db.flush()
    
    async def get_user_stats(self, db: AsyncSession, user_id: int) -> UserStats:
        """Get user statistics"""
        # Total bots
        total_bots_query = (
            select(func.count(Bot.id))
            .where(
                and_(
                    Bot.owner_id == user_id,
                    Bot.status != BotStatus.DELETED.value
                )
            )
        )
        total_bots_result = await db.execute(total_bots_query)
        total_bots = total_bots_result.scalar()
        
        # Active bots
        active_bots_query = (
            select(func.count(Bot.id))
            .where(
                and_(
                    Bot.owner_id == user_id,
                    Bot.status == BotStatus.ACTIVE.value
                )
            )
        )
        active_bots_result = await db.execute(active_bots_query)
        active_bots = active_bots_result.scalar()
        
        # Total subscribers across all bots
        total_subscribers_query = (
            select(func.sum(Bot.total_subscribers))
            .where(
                and_(
                    Bot.owner_id == user_id,
                    Bot.status != BotStatus.DELETED.value
                )
            )
        )
        total_subscribers_result = await db.execute(total_subscribers_query)
        total_subscribers = total_subscribers_result.scalar() or 0
        
        # Messages sent across all bots
        messages_sent_query = (
            select(func.sum(Bot.messages_sent))
            .where(
                and_(
                    Bot.owner_id == user_id,
                    Bot.status != BotStatus.DELETED.value
                )
            )
        )
        messages_sent_result = await db.execute(messages_sent_query)
        messages_sent = messages_sent_result.scalar() or 0
        
        # Link clicks (from analytics)
        from app.models.analytics import LinkClick
        link_clicks_query = (
            select(func.count(LinkClick.id))
            .join(Bot, LinkClick.bot_id == Bot.id)
            .where(Bot.owner_id == user_id)
        )
        link_clicks_result = await db.execute(link_clicks_query)
        link_clicks = link_clicks_result.scalar()
        
        return UserStats(
            total_bots=total_bots,
            active_bots=active_bots,
            total_subscribers=total_subscribers,
            messages_sent=messages_sent,
            link_clicks=link_clicks
        )
    
    async def deactivate_user(self, db: AsyncSession, user_id: int) -> bool:
        """Deactivate user"""
        user = await self.get_or_404(db, user_id)
        user.is_active = False
        await db.flush()
        
        logger.info(f"Deactivated user {user_id}")
        return True
    
    async def get_recent_users(
        self, 
        db: AsyncSession, 
        limit: int = 10
    ) -> List[User]:
        """Get recently registered users"""
        query = (
            select(User)
            .where(User.is_active == True)
            .order_by(User.created_at.desc())
            .limit(limit)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_active_users_count(self, db: AsyncSession) -> int:
        """Get count of active users"""
        query = select(func.count(User.id)).where(User.is_active == True)
        result = await db.execute(query)
        return result.scalar()
    
    async def search_users(
        self, 
        db: AsyncSession, 
        query: str, 
        limit: int = 20
    ) -> List[User]:
        """Search users by username or name"""
        search_query = (
            select(User)
            .where(
                and_(
                    User.is_active == True,
                    or_(
                        User.username.ilike(f"%{query}%"),
                        User.first_name.ilike(f"%{query}%"),
                        User.last_name.ilike(f"%{query}%")
                    )
                )
            )
            .limit(limit)
        )
        
        result = await db.execute(search_query)
        return result.scalars().all()


# Global instance
user_service = UserService()
