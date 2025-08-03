"""
Message Service - бизнес-логика управления сообщениями
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_

from app.models.message import Message, Broadcast, BroadcastButton, MessageType, MessageStatus
from app.models.bot import Bot, BotSubscriber
from app.schemas.message import MessageCreate, BroadcastCreate, BroadcastUpdate
from app.services.base import BaseService
from app.core.exceptions import MessageNotFoundError, ValidationError, BroadcastNotFoundError
from app.utils.utm import add_utm_to_text, generate_campaign_name

logger = logging.getLogger(__name__)


class MessageService(BaseService):
    """Service for message management"""
    
    async def create_message(
        self, 
        db: AsyncSession, 
        bot_id: int, 
        message_data: MessageCreate
    ) -> Message:
        """Create new message"""
        try:
            message = Message(
                bot_id=bot_id,
                recipient_id=message_data.recipient_id,
                content=message_data.content,
                message_type=message_data.message_type.value,
                utm_source=message_data.utm_source,
                utm_campaign=message_data.utm_campaign,
                utm_medium=message_data.utm_medium,
                utm_content=message_data.utm_content,
                scheduled_at=message_data.scheduled_at,
                metadata=message_data.metadata,
                status=MessageStatus.SENT.value if not message_data.scheduled_at else MessageStatus.SCHEDULED.value
            )
            
            if not message_data.scheduled_at:
                message.sent_at = datetime.utcnow()
            
            db.add(message)
            await db.flush()
            await db.refresh(message)
            
            logger.info(f"Created message {message.id} for bot {bot_id}")
            return message
            
        except Exception as e:
            logger.error(f"Error creating message: {e}")
            raise
    
    async def get_bot_messages(
        self, 
        db: AsyncSession, 
        bot_id: int, 
        skip: int = 0, 
        limit: int = 100,
        message_type: Optional[MessageType] = None
    ) -> List[Message]:
        """Get messages for bot"""
        query = select(Message).where(Message.bot_id == bot_id)
        
        if message_type:
            query = query.where(Message.message_type == message_type.value)
        
        query = query.order_by(Message.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def create_broadcast(
        self, 
        db: AsyncSession, 
        bot_id: int, 
        broadcast_data: BroadcastCreate
    ) -> Broadcast:
        """Create new broadcast"""
        try:
            # Generate campaign name if not provided
            if not broadcast_data.utm_campaign:
                campaign_name = generate_campaign_name("broadcast")
            else:
                campaign_name = broadcast_data.utm_campaign
            
            broadcast = Broadcast(
                bot_id=bot_id,
                title=broadcast_data.title,
                content=broadcast_data.content,
                photo_url=str(broadcast_data.photo_url) if broadcast_data.photo_url else None,
                document_url=str(broadcast_data.document_url) if broadcast_data.document_url else None,
                utm_source=broadcast_data.utm_source,
                utm_campaign=campaign_name,
                utm_medium=broadcast_data.utm_medium,
                scheduled_at=broadcast_data.scheduled_at,
                target_audience=broadcast_data.target_audience,
                send_delay=broadcast_data.send_delay,
                status=MessageStatus.SCHEDULED.value if broadcast_data.scheduled_at else MessageStatus.DRAFT.value
            )
            
            db.add(broadcast)
            await db.flush()
            await db.refresh(broadcast)
            
            # Add buttons if provided
            if broadcast_data.buttons:
                for button_data in broadcast_data.buttons:
                    button = BroadcastButton(
                        broadcast_id=broadcast.id,
                        text=button_data.text,
                        url=str(button_data.url) if button_data.url else None,
                        callback_data=button_data.callback_data,
                        row=button_data.row,
                        column=button_data.column
                    )
                    db.add(button)
            
            await db.flush()
            
            logger.info(f"Created broadcast {broadcast.id} for bot {bot_id}")
            return broadcast
            
        except Exception as e:
            logger.error(f"Error creating broadcast: {e}")
            raise
    
    async def get_broadcast(self, db: AsyncSession, broadcast_id: int) -> Broadcast:
        """Get broadcast by ID"""
        query = select(Broadcast).where(Broadcast.id == broadcast_id)
        result = await db.execute(query)
        broadcast = result.scalar_one_or_none()
        
        if not broadcast:
            raise BroadcastNotFoundError("Broadcast not found")
        
        return broadcast
    
    async def get_bot_broadcasts(
        self, 
        db: AsyncSession, 
        bot_id: int, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[MessageStatus] = None
    ) -> List[Broadcast]:
        """Get broadcasts for bot"""
        query = select(Broadcast).where(Broadcast.bot_id == bot_id)
        
        if status:
            query = query.where(Broadcast.status == status.value)
        
        query = query.order_by(Broadcast.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def update_broadcast(
        self, 
        db: AsyncSession, 
        broadcast_id: int, 
        broadcast_data: BroadcastUpdate
    ) -> Broadcast:
        """Update broadcast"""
        broadcast = await self.get_broadcast(db, broadcast_id)
        
        # Check if broadcast can be updated
        if broadcast.status in [MessageStatus.SENDING.value, MessageStatus.SENT.value]:
            raise ValidationError("Cannot update broadcast that is sending or sent")
        
        update_data = broadcast_data.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if field in ['photo_url', 'document_url'] and value:
                value = str(value)
            setattr(broadcast, field, value)
        
        await db.flush()
        await db.refresh(broadcast)
        
        logger.info(f"Updated broadcast {broadcast_id}")
        return broadcast
    
    async def send_broadcast(self, db: AsyncSession, broadcast_id: int) -> Dict[str, Any]:
        """Send broadcast to all recipients"""
        broadcast = await self.get_broadcast(db, broadcast_id)
        
        # Check broadcast status
        if broadcast.status != MessageStatus.DRAFT.value:
            raise ValidationError("Only draft broadcasts can be sent")
        
        # Get recipients
        recipients = await self._get_broadcast_recipients(db, broadcast)
        
        if not recipients:
            raise ValidationError("No recipients found for broadcast")
        
        # Update broadcast status and recipients count
        broadcast.status = MessageStatus.SENDING.value
        broadcast.total_recipients = len(recipients)
        
        await db.flush()
        
        # Process content - add UTM tracking
        processed_content = add_utm_to_text(
            broadcast.content,
            source=broadcast.utm_source or "broadcast",
            campaign=broadcast.utm_campaign or f"broadcast_{broadcast.id}",
            medium=broadcast.utm_medium or "telegram"
        )
        
        # Here we would typically queue the broadcast for background processing
        # For now, we'll return the data for the bot manager to handle
        
        return {
            "broadcast_id": broadcast.id,
            "recipients": recipients,
            "content": processed_content,
            "photo_url": broadcast.photo_url,
            "document_url": broadcast.document_url,
            "send_delay": broadcast.send_delay,
            "utm_params": {
                "source": broadcast.utm_source,
                "campaign": broadcast.utm_campaign,
                "medium": broadcast.utm_medium
            }
        }
    
    async def update_broadcast_stats(
        self, 
        db: AsyncSession, 
        broadcast_id: int, 
        successful_sends: int, 
        failed_sends: int
    ) -> Broadcast:
        """Update broadcast statistics"""
        broadcast = await self.get_broadcast(db, broadcast_id)
        
        broadcast.successful_sends = successful_sends
        broadcast.failed_sends = failed_sends
        broadcast.status = MessageStatus.SENT.value
        broadcast.sent_at = datetime.utcnow()
        
        await db.flush()
        await db.refresh(broadcast)
        
        logger.info(f"Updated broadcast {broadcast_id} stats: {successful_sends} success, {failed_sends} failed")
        return broadcast
    
    async def cancel_broadcast(self, db: AsyncSession, broadcast_id: int) -> Broadcast:
        """Cancel scheduled broadcast"""
        broadcast = await self.get_broadcast(db, broadcast_id)
        
        if broadcast.status not in [MessageStatus.DRAFT.value, MessageStatus.SCHEDULED.value]:
            raise ValidationError("Cannot cancel broadcast that is already sending or sent")
        
        broadcast.status = MessageStatus.CANCELLED.value
        
        await db.flush()
        await db.refresh(broadcast)
        
        logger.info(f"Cancelled broadcast {broadcast_id}")
        return broadcast
    
    async def get_scheduled_broadcasts(self, db: AsyncSession) -> List[Broadcast]:
        """Get broadcasts scheduled to be sent"""
        now = datetime.utcnow()
        
        query = (
            select(Broadcast)
            .where(
                and_(
                    Broadcast.status == MessageStatus.SCHEDULED.value,
                    Broadcast.scheduled_at <= now
                )
            )
            .order_by(Broadcast.scheduled_at)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_message_stats(
        self, 
        db: AsyncSession, 
        bot_id: int, 
        days: int = 30
    ) -> Dict[str, Any]:
        """Get message statistics for bot"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Total messages
        total_query = (
            select(func.count(Message.id))
            .where(
                and_(
                    Message.bot_id == bot_id,
                    Message.created_at >= start_date
                )
            )
        )
        total_result = await db.execute(total_query)
        total_messages = total_result.scalar()
        
        # Messages by type
        by_type_query = (
            select(Message.message_type, func.count(Message.id))
            .where(
                and_(
                    Message.bot_id == bot_id,
                    Message.created_at >= start_date
                )
            )
            .group_by(Message.message_type)
        )
        by_type_result = await db.execute(by_type_query)
        by_type = {row[0]: row[1] for row in by_type_result.fetchall()}
        
        # Unique recipients
        unique_recipients_query = (
            select(func.count(func.distinct(Message.recipient_id)))
            .where(
                and_(
                    Message.bot_id == bot_id,
                    Message.created_at >= start_date,
                    Message.recipient_id.isnot(None)
                )
            )
        )
        unique_recipients_result = await db.execute(unique_recipients_query)
        unique_recipients = unique_recipients_result.scalar()
        
        return {
            "total_messages": total_messages,
            "unique_recipients": unique_recipients,
            "by_type": by_type,
            "period_days": days
        }
    
    async def _get_broadcast_recipients(
        self, 
        db: AsyncSession, 
        broadcast: Broadcast
    ) -> List[BotSubscriber]:
        """Get recipients for broadcast based on targeting"""
        query = (
            select(BotSubscriber)
            .where(
                and_(
                    BotSubscriber.bot_id == broadcast.bot_id,
                    BotSubscriber.is_active == True
                )
            )
        )
        
        # Apply targeting filters if specified
        if broadcast.target_audience:
            filters = broadcast.target_audience
            
            # Filter by UTM source
            if "utm_source" in filters:
                query = query.where(BotSubscriber.utm_source.in_(filters["utm_source"]))
            
            # Filter by join date
            if "joined_after" in filters:
                join_date = datetime.fromisoformat(filters["joined_after"])
                query = query.where(BotSubscriber.joined_at >= join_date)
            
            # Filter by bot interaction
            if "bot_started_only" in filters and filters["bot_started_only"]:
                query = query.where(BotSubscriber.bot_started == True)
            
            # Filter by activity
            if "active_days" in filters:
                active_since = datetime.utcnow() - timedelta(days=filters["active_days"])
                query = query.where(BotSubscriber.last_activity_at >= active_since)
        
        result = await db.execute(query)
        return result.scalars().all()


# Global instance
message_service = MessageService()
