"""
Analytics Endpoints - аналитика и статистика
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.analytics_service import analytics_service
from app.services.bot_service import bot_service
from app.schemas.analytics import (
    AnalyticsEvent, AnalyticsEventInDB, LinkClickCreate, LinkClick,
    DailyStats, PeriodStats, AnalyticsDashboard, UTMStats,
    ReportRequest, ExportRequest
)
from app.schemas.user import User
from app.api.v1.auth import get_current_user
from app.core.exceptions import BotNotFoundError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/{bot_id}/events", response_model=AnalyticsEventInDB)
async def track_event(
    bot_id: int,
    event: AnalyticsEvent,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Track analytics event"""
    try:
        # Verify bot ownership
        await bot_service.get_bot(db, bot_id, current_user.id)
        
        # Track event
        analytics_record = await analytics_service.track_event(db, bot_id, event)
        await db.commit()
        
        return analytics_record
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except Exception as e:
        logger.error(f"Error tracking event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track event"
        )


@router.post("/{bot_id}/link-clicks", response_model=LinkClick)
async def track_link_click(
    bot_id: int,
    click_data: LinkClickCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Track link click"""
    try:
        # Verify bot ownership
        await bot_service.get_bot(db, bot_id, current_user.id)
        
        # Track click
        click_record = await analytics_service.track_link_click(db, bot_id, click_data)
        await db.commit()
        
        return click_record
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except Exception as e:
        logger.error(f"Error tracking link click: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track link click"
        )


@router.get("/{bot_id}/dashboard", response_model=AnalyticsDashboard)
async def get_dashboard(
    bot_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get analytics dashboard data"""
    try:
        # Verify bot ownership
        await bot_service.get_bot(db, bot_id, current_user.id)
        
        # Get dashboard data
        dashboard_data = await analytics_service.get_dashboard_data(db, bot_id)
        
        return dashboard_data
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dashboard data"
        )


@router.get("/{bot_id}/daily-stats", response_model=DailyStats)
async def get_daily_stats(
    bot_id: int,
    target_date: date = Query(default_factory=date.today),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get daily statistics"""
    try:
        # Verify bot ownership
        await bot_service.get_bot(db, bot_id, current_user.id)
        
        # Get daily stats
        daily_stats = await analytics_service.get_daily_stats(db, bot_id, target_date)
        
        return daily_stats
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except Exception as e:
        logger.error(f"Error getting daily stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get daily statistics"
        )


@router.get("/{bot_id}/period-stats", response_model=PeriodStats)
async def get_period_stats(
    bot_id: int,
    start_date: date = Query(..., description="Start date for period"),
    end_date: date = Query(..., description="End date for period"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get statistics for a specific period"""
    try:
        # Verify bot ownership
        await bot_service.get_bot(db, bot_id, current_user.id)
        
        # Validate date range
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before end date"
            )
        
        if (end_date - start_date).days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date range cannot exceed 365 days"
            )
        
        # Get period stats
        period_stats = await analytics_service.get_period_stats(
            db, bot_id, start_date, end_date
        )
        
        return period_stats
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting period stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get period statistics"
        )


@router.get("/{bot_id}/utm-stats", response_model=List[UTMStats])
async def get_utm_stats(
    bot_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get UTM tracking statistics"""
    try:
        # Verify bot ownership
        await bot_service.get_bot(db, bot_id, current_user.id)
        
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Get UTM stats
        utm_stats = await analytics_service._get_top_utm_sources(
            db, bot_id, start_date, end_date
        )
        
        return utm_stats
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except Exception as e:
        logger.error(f"Error getting UTM stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get UTM statistics"
        )


@router.post("/{bot_id}/reports")
async def generate_report(
    bot_id: int,
    report_request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate analytics report"""
    try:
        # Verify bot ownership
        await bot_service.get_bot(db, bot_id, current_user.id)
        
        # Validate date range
        if report_request.start_date > report_request.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before end date"
            )
        
        # Get period stats for report
        period_stats = await analytics_service.get_period_stats(
            db, bot_id, report_request.start_date, report_request.end_date
        )
        
        # Format based on requested format
        if report_request.format == "json":
            return {
                "report_type": "analytics",
                "bot_id": bot_id,
                "period": {
                    "start_date": report_request.start_date.isoformat(),
                    "end_date": report_request.end_date.isoformat()
                },
                "data": period_stats,
                "generated_at": datetime.utcnow().isoformat()
            }
        elif report_request.format == "csv":
            # В реальной реализации здесь будет генерация CSV
            return {
                "message": "CSV report generation not implemented yet",
                "download_url": f"/analytics/{bot_id}/reports/download/csv"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported report format"
            )
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report"
        )


@router.get("/{bot_id}/export")
async def export_data(
    bot_id: int,
    data_type: str = Query(..., regex="^(subscribers|messages|analytics|link_clicks)$"),
    format: str = Query("csv", regex="^(csv|json|excel)$"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Export bot data"""
    try:
        # Verify bot ownership
        await bot_service.get_bot(db, bot_id, current_user.id)
        
        # Set default date range if not provided
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Validate date range
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before end date"
            )
        
        # Generate export data based on type
        export_data = {
            "export_type": data_type,
            "bot_id": bot_id,
            "format": format,
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "generated_at": datetime.utcnow().isoformat()
        }
        
        if data_type == "subscribers":
            subscribers = await bot_service.get_bot_subscribers(
                db, bot_id, skip=0, limit=10000, active_only=False
            )
            export_data["data"] = [
                {
                    "user_id": sub.user_id,
                    "username": sub.username,
                    "display_name": sub.display_name,
                    "joined_at": sub.joined_at.isoformat(),
                    "is_active": sub.is_active,
                    "utm_source": sub.utm_source,
                    "utm_campaign": sub.utm_campaign
                }
                for sub in subscribers
            ]
        elif data_type == "analytics":
            # В реальной реализации здесь будет запрос аналитики
            export_data["data"] = []
            export_data["message"] = "Analytics export not fully implemented"
        else:
            export_data["data"] = []
            export_data["message"] = f"{data_type} export not implemented yet"
        
        return export_data
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export data"
        )


@router.get("/{bot_id}/real-time")
async def get_real_time_stats(
    bot_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get real-time statistics"""
    try:
        # Verify bot ownership
        bot = await bot_service.get_bot(db, bot_id, current_user.id)
        
        # Get bot instance from manager
        bot_instance = bot_manager.get_bot_instance(bot_id)
        
        real_time_stats = {
            "bot_id": bot_id,
            "timestamp": datetime.utcnow().isoformat(),
            "status": bot.status,
            "is_running": bot_instance is not None,
            "total_subscribers": bot.total_subscribers,
            "messages_sent": bot.messages_sent,
            "last_activity": bot.last_ping_at.isoformat() if bot.last_ping_at else None
        }
        
        if bot_instance:
            real_time_stats.update({
                "instance_created_at": bot_instance.created_at.isoformat(),
                "last_ping": bot_instance.last_ping.isoformat(),
                "active_handlers": bot_instance.active
            })
        
        return real_time_stats
        
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    except Exception as e:
        logger.error(f"Error getting real-time stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get real-time statistics"
        )
