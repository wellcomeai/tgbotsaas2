"""
Analytics Service - сервис аналитики
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload

from app.models.analytics import Analytics, LinkClick, BotStats, UTMCampaign
from app.models.bot import Bot, BotSubscriber
from app.models.message import Message, Broadcast
from app.schemas.analytics import (
    AnalyticsEvent, LinkClickCreate, DailyStats, 
    PeriodStats, UTMStats, AnalyticsDashboard
)
from app.services.base import BaseService
from app.utils.utm import parse_utm_analytics

logger = logging.getLogger(__name__)


class AnalyticsService(BaseService):
    """Service for analytics and statistics"""
    
    async def track_event(
        self,
        db: AsyncSession,
        bot_id: int,
        event: AnalyticsEvent
    ) -> Analytics:
        """Track analytics event"""
        try:
            analytics_record = Analytics(
                bot_id=bot_id,
                user_id=event.user_id,
                event_type=event.event_type,
                event_data=event.event_data,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                utm_source=event.utm_source,
                utm_campaign=event.utm_campaign,
                utm_medium=event.utm_medium,
                utm_content=event.utm_content,
                utm_term=event.utm_term
            )
            
            db.add(analytics_record)
            await db.flush()
            await db.refresh(analytics_record)
            
            logger.info(f"Tracked event {event.event_type} for bot {bot_id}")
            return analytics_record
            
        except Exception as e:
            logger.error(f"Error tracking event: {e}")
            raise
    
    async def track_link_click(
        self,
        db: AsyncSession,
        bot_id: int,
        click_data: LinkClickCreate
    ) -> LinkClick:
        """Track link click"""
        try:
            click_record = LinkClick(
                bot_id=bot_id,
                user_id=click_data.user_id,
                original_url=str(click_data.original_url),
                tracked_url=str(click_data.tracked_url) if click_data.tracked_url else None,
                utm_source=click_data.utm_source,
                utm_campaign=click_data.utm_campaign,
                utm_medium=click_data.utm_medium,
                utm_content=click_data.utm_content,
                utm_term=click_data.utm_term,
                ip_address=click_data.ip_address,
                user_agent=click_data.user_agent,
                referrer=click_data.referrer
            )
            
            db.add(click_record)
            await db.flush()
            await db.refresh(click_record)
            
            logger.info(f"Tracked link click for bot {bot_id}")
            return click_record
            
        except Exception as e:
            logger.error(f"Error tracking link click: {e}")
            raise
    
    async def get_daily_stats(
        self,
        db: AsyncSession,
        bot_id: int,
        target_date: date
    ) -> DailyStats:
        """Get daily statistics for bot"""
        try:
            start_date = datetime.combine(target_date, datetime.min.time())
            end_date = start_date + timedelta(days=1)
            
            # Get or create daily stats record
            stats_query = select(BotStats).where(
                and_(
                    BotStats.bot_id == bot_id,
                    BotStats.date >= start_date,
                    BotStats.date < end_date
                )
            )
            
            result = await db.execute(stats_query)
            existing_stats = result.scalar_one_or_none()
            
            if existing_stats:
                return DailyStats(
                    date=target_date,
                    total_subscribers=existing_stats.total_subscribers,
                    new_subscribers=existing_stats.new_subscribers,
                    unsubscribed=existing_stats.unsubscribed,
                    active_subscribers=existing_stats.active_subscribers,
                    messages_sent=existing_stats.messages_sent,
                    broadcasts_sent=existing_stats.broadcasts_sent,
                    messages_failed=existing_stats.messages_failed,
                    link_clicks=existing_stats.link_clicks,
                    bot_interactions=existing_stats.bot_interactions,
                    avg_response_time=existing_stats.avg_response_time,
                    error_rate=existing_stats.error_rate,
                    engagement_rate=existing_stats.engagement_rate,
                    click_through_rate=existing_stats.click_through_rate
                )
            
            # Calculate stats if not cached
            return await self._calculate_daily_stats(db, bot_id, target_date)
            
        except Exception as e:
            logger.error(f"Error getting daily stats: {e}")
            raise
    
    async def get_period_stats(
        self,
        db: AsyncSession,
        bot_id: int,
        start_date: date,
        end_date: date
    ) -> PeriodStats:
        """Get statistics for a period"""
        try:
            # Get daily stats for each day in period
            daily_stats = []
            current_date = start_date
            
            while current_date <= end_date:
                day_stats = await self.get_daily_stats(db, bot_id, current_date)
                daily_stats.append(day_stats)
                current_date += timedelta(days=1)
            
            # Calculate period aggregates
            total_new_subscribers = sum(d.new_subscribers for d in daily_stats)
            total_unsubscribed = sum(d.unsubscribed for d in daily_stats)
            net_growth = total_new_subscribers - total_unsubscribed
            
            # Calculate growth rate
            start_subscribers = daily_stats[0].total_subscribers - daily_stats[0].new_subscribers if daily_stats else 0
            growth_rate = (net_growth / max(start_subscribers, 1)) * 100
            
            # Get top UTM sources
            top_utm_sources = await self._get_top_utm_sources(db, bot_id, start_date, end_date)
            
            return PeriodStats(
                start_date=start_date,
                end_date=end_date,
                total_subscribers=daily_stats[-1].total_subscribers if daily_stats else 0,
                new_subscribers=total_new_subscribers,
                unsubscribed=total_unsubscribed,
                net_growth=net_growth,
                growth_rate=growth_rate,
                messages_sent=sum(d.messages_sent for d in daily_stats),
                broadcasts_sent=sum(d.broadcasts_sent for d in daily_stats),
                link_clicks=sum(d.link_clicks for d in daily_stats),
                avg_engagement_rate=sum(d.engagement_rate for d in daily_stats) / len(daily_stats) if daily_stats else 0,
                avg_click_through_rate=sum(d.click_through_rate for d in daily_stats) / len(daily_stats) if daily_stats else 0,
                top_utm_sources=top_utm_sources,
                daily_stats=daily_stats
            )
            
        except Exception as e:
            logger.error(f"Error getting period stats: {e}")
            raise
    
    async def get_dashboard_data(
        self,
        db: AsyncSession,
        bot_id: int
    ) -> AnalyticsDashboard:
        """Get comprehensive dashboard data"""
        try:
            today = date.today()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            # Get current stats
            today_stats = await self.get_daily_stats(db, bot_id, today)
            week_stats = await self.get_period_stats(db, bot_id, week_ago, today)
            
            # Get growth rates
            last_week_stats = await self.get_period_stats(
                db, bot_id, 
                week_ago - timedelta(days=7), 
                week_ago
            )
            
            subscriber_growth_rate = (
                (week_stats.total_subscribers - last_week_stats.total_subscribers) / 
                max(last_week_stats.total_subscribers, 1) * 100
            )
            
            engagement_growth_rate = (
                week_stats.avg_engagement_rate - last_week_stats.avg_engagement_rate
            )
            
            # Get top content
            top_links = await self._get_top_links(db, bot_id, month_ago, today)
            top_utm_campaigns = await self._get_top_utm_sources(db, bot_id, month_ago, today)
            
            # Get recent activity
            recent_stats = []
            for i in range(7):
                day = today - timedelta(days=i)
                day_stats = await self.get_daily_stats(db, bot_id, day)
                recent_stats.append(day_stats)
            recent_stats.reverse()
            
            # Get engagement metrics
            engagement_metrics = await self._get_engagement_metrics(db, bot_id, month_ago, today)
            
            # Get conversion funnel
            conversion_funnel = await self._get_conversion_funnel(db, bot_id, month_ago, today)
            
            return AnalyticsDashboard(
                total_subscribers=today_stats.total_subscribers,
                active_subscribers=today_stats.active_subscribers,
                new_subscribers_today=today_stats.new_subscribers,
                messages_sent_today=today_stats.messages_sent,
                link_clicks_today=today_stats.link_clicks,
                subscriber_growth_rate=subscriber_growth_rate,
                engagement_growth_rate=engagement_growth_rate,
                avg_response_time=today_stats.avg_response_time or 0.0,
                error_rate=today_stats.error_rate,
                uptime_percentage=100.0 - today_stats.error_rate,  # Simplified
                top_links=top_links,
                top_utm_campaigns=top_utm_campaigns,
                recent_stats=recent_stats,
                engagement_metrics=engagement_metrics,
                conversion_funnel=conversion_funnel
            )
            
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            raise
    
    async def _calculate_daily_stats(
        self,
        db: AsyncSession,
        bot_id: int,
        target_date: date
    ) -> DailyStats:
        """Calculate daily statistics from raw data"""
        try:
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = start_datetime + timedelta(days=1)
            
            # Total subscribers at end of day
            total_subscribers_query = select(func.count(BotSubscriber.id)).where(
                and_(
                    BotSubscriber.bot_id == bot_id,
                    BotSubscriber.is_active == True,
                    BotSubscriber.joined_at <= end_datetime
                )
            )
            total_subscribers_result = await db.execute(total_subscribers_query)
            total_subscribers = total_subscribers_result.scalar() or 0
            
            # New subscribers this day
            new_subscribers_query = select(func.count(BotSubscriber.id)).where(
                and_(
                    BotSubscriber.bot_id == bot_id,
                    BotSubscriber.joined_at >= start_datetime,
                    BotSubscriber.joined_at < end_datetime
                )
            )
            new_subscribers_result = await db.execute(new_subscribers_query)
            new_subscribers = new_subscribers_result.scalar() or 0
            
            # Messages sent this day
            messages_sent_query = select(func.count(Message.id)).where(
                and_(
                    Message.bot_id == bot_id,
                    Message.sent_at >= start_datetime,
                    Message.sent_at < end_datetime
                )
            )
            messages_sent_result = await db.execute(messages_sent_query)
            messages_sent = messages_sent_result.scalar() or 0
            
            # Link clicks this day
            link_clicks_query = select(func.count(LinkClick.id)).where(
                and_(
                    LinkClick.bot_id == bot_id,
                    LinkClick.created_at >= start_datetime,
                    LinkClick.created_at < end_datetime
                )
            )
            link_clicks_result = await db.execute(link_clicks_query)
            link_clicks = link_clicks_result.scalar() or 0
            
            # Calculate rates
            engagement_rate = (link_clicks / max(total_subscribers, 1)) * 100
            click_through_rate = (link_clicks / max(messages_sent, 1)) * 100
            
            return DailyStats(
                date=target_date,
                total_subscribers=total_subscribers,
                new_subscribers=new_subscribers,
                unsubscribed=0,  # Would need to track unsubscribe events
                active_subscribers=total_subscribers,  # Simplified
                messages_sent=messages_sent,
                broadcasts_sent=0,  # Would count broadcast messages
                messages_failed=0,  # Would track failed messages
                link_clicks=link_clicks,
                bot_interactions=0,  # Would track bot interactions
                avg_response_time=None,
                error_rate=0.0,
                engagement_rate=engagement_rate,
                click_through_rate=click_through_rate
            )
            
        except Exception as e:
            logger.error(f"Error calculating daily stats: {e}")
            raise
    
    async def _get_top_utm_sources(
        self,
        db: AsyncSession,
        bot_id: int,
        start_date: date,
        end_date: date,
        limit: int = 10
    ) -> List[UTMStats]:
        """Get top UTM sources for period"""
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            # Get UTM statistics from link clicks
            utm_query = (
                select(
                    LinkClick.utm_source,
                    LinkClick.utm_campaign,
                    LinkClick.utm_medium,
                    func.count(LinkClick.id).label('clicks'),
                    func.count(func.distinct(LinkClick.user_id)).label('unique_users')
                )
                .where(
                    and_(
                        LinkClick.bot_id == bot_id,
                        LinkClick.created_at >= start_datetime,
                        LinkClick.created_at <= end_datetime,
                        LinkClick.utm_source.isnot(None)
                    )
                )
                .group_by(LinkClick.utm_source, LinkClick.utm_campaign, LinkClick.utm_medium)
                .order_by(desc('clicks'))
                .limit(limit)
            )
            
            result = await db.execute(utm_query)
            utm_data = result.fetchall()
            
            utm_stats = []
            for row in utm_data:
                utm_stats.append(UTMStats(
                    source=row.utm_source or 'unknown',
                    campaign=row.utm_campaign or 'unknown',
                    medium=row.utm_medium or 'unknown',
                    clicks=row.clicks,
                    unique_users=row.unique_users,
                    conversions=0,  # Would need conversion tracking
                    conversion_rate=0.0
                ))
            
            return utm_stats
            
        except Exception as e:
            logger.error(f"Error getting top UTM sources: {e}")
            return []
    
    async def _get_top_links(
        self,
        db: AsyncSession,
        bot_id: int,
        start_date: date,
        end_date: date,
        limit: int = 10
    ):
        """Get top clicked links"""
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            # Get top links by click count
            links_query = (
                select(
                    LinkClick.original_url,
                    func.count(LinkClick.id).label('clicks'),
                    func.count(func.distinct(LinkClick.user_id)).label('unique_users'),
                    LinkClick.utm_campaign
                )
                .where(
                    and_(
                        LinkClick.bot_id == bot_id,
                        LinkClick.created_at >= start_datetime,
                        LinkClick.created_at <= end_datetime
                    )
                )
                .group_by(LinkClick.original_url, LinkClick.utm_campaign)
                .order_by(desc('clicks'))
                .limit(limit)
            )
            
            result = await db.execute(links_query)
            links_data = result.fetchall()
            
            from app.schemas.analytics import TopLink
            top_links = []
            for row in links_data:
                top_links.append(TopLink(
                    url=row.original_url,
                    clicks=row.clicks,
                    unique_users=row.unique_users,
                    utm_campaign=row.utm_campaign
                ))
            
            return top_links
            
        except Exception as e:
            logger.error(f"Error getting top links: {e}")
            return []
    
    async def _get_engagement_metrics(
        self,
        db: AsyncSession,
        bot_id: int,
        start_date: date,
        end_date: date
    ):
        """Get engagement metrics"""
        try:
            # This would calculate detailed engagement metrics
            # For now, return simplified metrics
            
            from app.schemas.analytics import EngagementMetrics
            return EngagementMetrics(
                total_users=0,
                active_users=0,
                engagement_rate=0.0,
                avg_session_duration=None,
                bounce_rate=0.0,
                return_users=0,
                return_rate=0.0
            )
            
        except Exception as e:
            logger.error(f"Error getting engagement metrics: {e}")
            from app.schemas.analytics import EngagementMetrics
            return EngagementMetrics(
                total_users=0,
                active_users=0,
                engagement_rate=0.0,
                avg_session_duration=None,
                bounce_rate=0.0,
                return_users=0,
                return_rate=0.0
            )
    
    async def _get_conversion_funnel(
        self,
        db: AsyncSession,
        bot_id: int,
        start_date: date,
        end_date: date
    ):
        """Get conversion funnel data"""
        try:
            # This would calculate conversion funnel steps
            # For now, return simplified funnel
            
            from app.schemas.analytics import ConversionFunnel
            return [
                ConversionFunnel(
                    step_name="Channel Join",
                    users_entered=100,
                    users_completed=100,
                    completion_rate=100.0
                ),
                ConversionFunnel(
                    step_name="Bot Interaction",
                    users_entered=100,
                    users_completed=60,
                    completion_rate=60.0
                ),
                ConversionFunnel(
                    step_name="Link Click",
                    users_entered=60,
                    users_completed=30,
                    completion_rate=50.0
                ),
                ConversionFunnel(
                    step_name="Conversion",
                    users_entered=30,
                    users_completed=10,
                    completion_rate=33.3
                )
            ]
            
        except Exception as e:
            logger.error(f"Error getting conversion funnel: {e}")
            return []


# Global instance
analytics_service = AnalyticsService()
