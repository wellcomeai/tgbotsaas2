"""
Bot Management Endpoints - управление ботами
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.bot_service import bot_service
from app.services.message_service import message_service
from app.telegram.bot_manager import bot_manager
from app.schemas.bot import (
    Bot, BotCreate, BotUpdate, BotWithStats, BotSubscriber, 
    BotConfigUpdate, BotStats
)
from app.schemas.message import Broadcast, BroadcastCreate, BroadcastUpdate
from app.schemas.user import User
from app.api.v1.auth import get_current_user
from app.core.exceptions import (
    BotNotFoundError, ValidationError, BotLimitReachedError
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=Bot)
async def create_bot(
    bot_data: BotCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new bot"""
    try:
        # Create bot in database
        new_bot = await bot_service.create_bot(db, bot_data, current_user.id)
        await db.commit()
        
        # Add bot to manager in background
        background_tasks.add_task(bot_manager.add_bot, new_bot)
        
        logger.info(f"Bot {new_bot.id} created for user {current_user.id}")
        return new_bot
        
    except BotLimitReachedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating bot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create bot"
        )


@router.get("/", response_model=List[Bot])
async def get_user_bots(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all bots for current user"""
    try:
        bots = await bot_service.get_user_bots(
            db, current_user.id, skip=skip, limit=limit
        )
        return bots
        
    except Exception as e:
        logger.error(f"Error getting user bots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get bots"
        )


@router.get("/{bot_id}", response_model=BotWithStats)
async def get_bot(
    bot_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get specific bot with statistics"""
    try:
        bot = await bot_service.get_bot(db, bot_id, current_user.id)
        
        # Get bot statistics (можно кешировать)
        stats = BotStats(
            total_subscribers=bot.total_subscribers,
            active_subscribers=bot.total_subscribers,  # Simplified
            new_subscribers_today=0,  # Would calculate from analytics
            messages_sent_today=0,
            messages_sent_total=bot.messages_sent,
            link_clicks_today=0,
            link_clicks_total=0,
            engagement_rate=0.0,
            error_rate=0.0,
            uptime_percentage=100.0
        )
        
        return BotWithStats(**bot.__dict__, stats=stats)
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except Exception as e:
        logger.error(f"Error getting bot {bot_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get bot"
        )


@router.put("/{bot_id}", response_model=Bot)
async def update_bot(
    bot_id: int,
    bot_update: BotUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update bot settings"""
    try:
        updated_bot = await bot_service.update_bot(
            db, bot_id, bot_update, current_user.id
        )
        await db.commit()
        
        return updated_bot
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating bot {bot_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update bot"
        )


@router.put("/{bot_id}/config", response_model=Bot)
async def update_bot_config(
    bot_id: int,
    config_update: BotConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update bot configuration"""
    try:
        updated_bot = await bot_service.update_bot_config(
            db, bot_id, config_update, current_user.id
        )
        await db.commit()
        
        return updated_bot
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except Exception as e:
        logger.error(f"Error updating bot config {bot_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update bot configuration"
        )


@router.delete("/{bot_id}")
async def delete_bot(
    bot_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete bot"""
    try:
        success = await bot_service.delete_bot(db, bot_id, current_user.id)
        
        if success:
            await db.commit()
            
            # Remove bot from manager in background
            background_tasks.add_task(bot_manager.remove_bot, bot_id)
            
            return {"message": "Bot deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete bot"
            )
            
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except Exception as e:
        logger.error(f"Error deleting bot {bot_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete bot"
        )


@router.post("/{bot_id}/restart")
async def restart_bot(
    bot_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Restart bot"""
    try:
        # Verify bot ownership
        await bot_service.get_bot(db, bot_id, current_user.id)
        
        # Restart bot in background
        background_tasks.add_task(bot_manager.restart_bot, bot_id)
        
        return {"message": "Bot restart initiated"}
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except Exception as e:
        logger.error(f"Error restarting bot {bot_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restart bot"
        )


@router.get("/{bot_id}/subscribers", response_model=List[BotSubscriber])
async def get_bot_subscribers(
    bot_id: int,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get bot subscribers"""
    try:
        # Verify bot ownership
        await bot_service.get_bot(db, bot_id, current_user.id)
        
        subscribers = await bot_service.get_bot_subscribers(
            db, bot_id, skip=skip, limit=limit, active_only=active_only
        )
        
        return subscribers
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except Exception as e:
        logger.error(f"Error getting bot subscribers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get subscribers"
        )


@router.post("/{bot_id}/broadcasts", response_model=Broadcast)
async def create_broadcast(
    bot_id: int,
    broadcast_data: BroadcastCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create broadcast for bot"""
    try:
        # Verify bot ownership
        await bot_service.get_bot(db, bot_id, current_user.id)
        
        broadcast = await message_service.create_broadcast(
            db, bot_id, broadcast_data
        )
        await db.commit()
        
        return broadcast
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating broadcast: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create broadcast"
        )


@router.get("/{bot_id}/broadcasts", response_model=List[Broadcast])
async def get_bot_broadcasts(
    bot_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get broadcasts for bot"""
    try:
        # Verify bot ownership
        await bot_service.get_bot(db, bot_id, current_user.id)
        
        broadcasts = await message_service.get_bot_broadcasts(
            db, bot_id, skip=skip, limit=limit
        )
        
        return broadcasts
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except Exception as e:
        logger.error(f"Error getting broadcasts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get broadcasts"
        )


@router.post("/{bot_id}/broadcasts/{broadcast_id}/send")
async def send_broadcast(
    bot_id: int,
    broadcast_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send broadcast"""
    try:
        # Verify bot ownership
        await bot_service.get_bot(db, bot_id, current_user.id)
        
        # Get broadcast data
        broadcast_info = await message_service.send_broadcast(db, broadcast_id)
        
        # Process broadcast in background
        # В реальной реализации здесь будет Celery task
        logger.info(f"Broadcast {broadcast_id} queued for sending")
        
        return {"message": "Broadcast queued for sending", "broadcast_id": broadcast_id}
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error sending broadcast: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send broadcast"
        )
