"""
Analytics Processing Tasks
"""

import logging
from datetime import datetime, timedelta, date
from celery import current_task
from app.tasks.celery_app import celery_app
from app.core.database import get_db
from app.services.analytics_service import analytics_service
from app.services.bot_service import bot_service

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="analytics_tasks.calculate_daily_stats")
def calculate_daily_stats_task(self, bot_id: int, target_date: str = None):
    """Calculate and cache daily statistics"""
    try:
        if target_date:
            target_date = datetime.fromisoformat(target_date).date()
        else:
            target_date = date.today()
        
        current_task.update_state(
            state='PROGRESS',
            meta={'message': f'Calculating daily stats for bot {bot_id} on {target_date}...'}
        )
        
        async def _calculate_stats():
            async for db in get_db():
                # Calculate daily stats
                stats = await analytics_service.get_daily_stats(db, bot_id, target_date)
                
                # Cache the results (если используем кэш)
                # await cache_manager.set_bot_stats_cache(bot_id, stats.__dict__, expire=3600)
                
                return stats.__dict__
        
        import asyncio
        result = asyncio.run(_calculate_stats())
        
        logger.info(f"Daily stats calculated for bot {bot_id} on {target_date}")
        return {
            'status': 'success',
            'data': result
        }
        
    except Exception as e:
        logger.error(f"Error calculating daily stats: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(name="analytics_tasks.update_all_bot_stats")
def update_all_bot_stats_task():
    """Update statistics for all active bots"""
    try:
        async def _update_all_stats():
            async for db in get_db():
                # Get all active bots
                active_bots = await bot_service.get_active_bots(db)
                
                today = date.today()
                processed_count = 0
                
                for bot in active_bots:
                    try:
                        # Calculate daily stats for each bot
                        await analytics_service.get_daily_stats(db, bot.id, today)
                        processed_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error updating stats for bot {bot.id}: {e}")
                
                return {
                    'total_bots': len(active_bots),
                    'processed': processed_count
                }
        
        import asyncio
        result = asyncio.run(_update_all_stats())
        
        logger.info(f"Updated stats for {result['processed']}/{result['total_bots']} bots")
        return {
            'status': 'success',
            'data': result
        }
        
    except Exception as e:
        logger.error(f"Error updating all bot stats: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(bind=True, name="analytics_tasks.generate_report")
def generate_report_task(self, bot_id: int, report_type: str, start_date: str, end_date: str):
    """Generate analytics report"""
    try:
        start_date = datetime.fromisoformat(start_date).date()
        end_date = datetime.fromisoformat(end_date).date()
        
        current_task.update_state(
            state='PROGRESS',
            meta={'message': f'Generating {report_type} report for bot {bot_id}...'}
        )
        
        async def _generate_report():
            async for db in get_db():
                if report_type == 'period_stats':
                    # Generate period statistics report
                    period_stats = await analytics_service.get_period_stats(
                        db, bot_id, start_date, end_date
                    )
                    
                    return {
                        'report_type': report_type,
                        'bot_id': bot_id,
                        'period': {
                            'start_date': start_date.isoformat(),
                            'end_date': end_date.isoformat()
                        },
                        'data': period_stats.__dict__,
                        'generated_at': datetime.utcnow().isoformat()
                    }
                
                elif report_type == 'dashboard':
                    # Generate dashboard report
                    dashboard_data = await analytics_service.get_dashboard_data(db, bot_id)
                    
                    return {
                        'report_type': report_type,
                        'bot_id': bot_id,
                        'data': dashboard_data.__dict__,
                        'generated_at': datetime.utcnow().isoformat()
                    }
                
                else:
                    raise ValueError(f"Unknown report type: {report_type}")
        
        import asyncio
        result = asyncio.run(_generate_report())
        
        logger.info(f"Generated {report_type} report for bot {bot_id}")
        return {
            'status': 'success',
            'data': result
        }
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(name="analytics_tasks.cleanup_old_analytics")
def cleanup_old_analytics_task(days_to_keep: int = 365):
    """Cleanup old analytics data"""
    try:
        async def _cleanup():
            async for db in get_db():
                from app.models.analytics import Analytics, LinkClick
                from sqlalchemy import delete
                
                cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
                
                # Delete old analytics events
                analytics_query = delete(Analytics).where(Analytics.created_at < cutoff_date)
                analytics_result = await db.execute(analytics_query)
                
                # Delete old link clicks
                clicks_query = delete(LinkClick).where(LinkClick.created_at < cutoff_date)
                clicks_result = await db.execute(clicks_query)
                
                await db.commit()
                
                return {
                    'analytics_deleted': analytics_result.rowcount,
                    'clicks_deleted': clicks_result.rowcount,
                    'cutoff_date': cutoff_date.isoformat()
                }
        
        import asyncio
        result = asyncio.run(_cleanup())
        
        logger.info(f"Cleaned up old analytics: {result}")
        return {
            'status': 'success',
            'data': result
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up analytics: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


# Periodic analytics tasks
from celery.schedules import crontab

celery_app.conf.beat_schedule.update({
    'update-daily-stats': {
        'task': 'analytics_tasks.update_all_bot_stats',
        'schedule': crontab(minute=0, hour=1),  # Daily at 1 AM
    },
    'cleanup-old-analytics': {
        'task': 'analytics_tasks.cleanup_old_analytics',
        'schedule': crontab(minute=0, hour=2, day_of_week=0),  # Weekly on Sunday at 2 AM
    },
})
