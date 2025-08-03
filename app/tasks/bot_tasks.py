"""
Bot Management Tasks
"""

import logging
from celery import current_task
from app.tasks.celery_app import celery_app
from app.core.database import get_db
from app.services.bot_service import bot_service
from app.telegram.bot_manager import bot_manager

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="bot_tasks.create_and_start_bot")
def create_and_start_bot_task(self, bot_id: int):
    """Create and start bot in manager"""
    try:
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'message': f'Starting bot {bot_id}...'}
        )
        
        # Get bot from database
        async def _create_bot():
            async for db in get_db():
                bot = await bot_service.get_bot(db, bot_id)
                success = await bot_manager.add_bot(bot)
                return success
        
        import asyncio
        success = asyncio.run(_create_bot())
        
        if success:
            logger.info(f"Bot {bot_id} started successfully")
            return {
                'status': 'success',
                'message': f'Bot {bot_id} started successfully'
            }
        else:
            logger.error(f"Failed to start bot {bot_id}")
            return {
                'status': 'error', 
                'message': f'Failed to start bot {bot_id}'
            }
            
    except Exception as e:
        logger.error(f"Error in create_and_start_bot_task: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(bind=True, name="bot_tasks.restart_bot")
def restart_bot_task(self, bot_id: int):
    """Restart bot task"""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'message': f'Restarting bot {bot_id}...'}
        )
        
        async def _restart_bot():
            return await bot_manager.restart_bot(bot_id)
        
        import asyncio
        success = asyncio.run(_restart_bot())
        
        if success:
            return {
                'status': 'success',
                'message': f'Bot {bot_id} restarted successfully'
            }
        else:
            return {
                'status': 'error',
                'message': f'Failed to restart bot {bot_id}'
            }
            
    except Exception as e:
        logger.error(f"Error restarting bot {bot_id}: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(bind=True, name="bot_tasks.health_check_all_bots")
def health_check_all_bots_task(self):
    """Health check for all bots"""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'message': 'Checking health of all bots...'}
        )
        
        async def _health_check():
            stats = bot_manager.get_stats()
            
            # Perform health checks
            unhealthy_bots = []
            for bot_id, bot_instance in bot_manager.bot_instances.items():
                try:
                    from app.utils.telegram import verify_bot_token
                    bot_info = await verify_bot_token(bot_instance.bot_token)
                    if not bot_info:
                        unhealthy_bots.append(bot_id)
                except Exception:
                    unhealthy_bots.append(bot_id)
            
            return {
                'total_bots': stats['total_bots'],
                'running_bots': stats['running_bots'],
                'unhealthy_bots': unhealthy_bots,
                'healthy_bots': stats['running_bots'] - len(unhealthy_bots)
            }
        
        import asyncio
        result = asyncio.run(_health_check())
        
        logger.info(f"Health check completed: {result}")
        return {
            'status': 'success',
            'data': result
        }
        
    except Exception as e:
        logger.error(f"Error in health check task: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(name="bot_tasks.cleanup_inactive_bots")
def cleanup_inactive_bots_task():
    """Cleanup inactive bots"""
    try:
        async def _cleanup():
            async for db in get_db():
                # Find bots that haven't pinged in 1 hour
                from datetime import datetime, timedelta
                from app.models.bot import Bot, BotStatus
                from sqlalchemy import select, and_
                
                cutoff_time = datetime.utcnow() - timedelta(hours=1)
                
                query = select(Bot).where(
                    and_(
                        Bot.status == BotStatus.ACTIVE.value,
                        Bot.last_ping_at < cutoff_time
                    )
                )
                
                result = await db.execute(query)
                inactive_bots = result.scalars().all()
                
                cleanup_count = 0
                for bot in inactive_bots:
                    # Remove from manager
                    success = await bot_manager.remove_bot(bot.id)
                    if success:
                        cleanup_count += 1
                
                return cleanup_count
        
        import asyncio
        cleanup_count = asyncio.run(_cleanup())
        
        logger.info(f"Cleaned up {cleanup_count} inactive bots")
        return {
            'status': 'success',
            'cleaned_up': cleanup_count
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup task: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


# Periodic tasks
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'health-check-bots': {
        'task': 'bot_tasks.health_check_all_bots',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'cleanup-inactive-bots': {
        'task': 'bot_tasks.cleanup_inactive_bots', 
        'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours
    },
}
