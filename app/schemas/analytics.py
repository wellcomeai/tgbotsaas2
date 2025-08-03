"""
Analytics Schemas - Pydantic схемы для аналитики
"""

from datetime import datetime, date
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, HttpUrl


class AnalyticsEvent(BaseModel):
    """Analytics event schema"""
    event_type: str
    event_data: Optional[Dict[str, Any]] = None
    user_id: Optional[int] = None
    utm_source: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AnalyticsEventInDB(AnalyticsEvent):
    """Analytics event with database fields"""
    id: int
    bot_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class LinkClickCreate(BaseModel):
    """Schema for creating link click"""
    user_id: int
    original_url: HttpUrl
    tracked_url: Optional[HttpUrl] = None
    utm_source: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referrer: Optional[str] = None


class LinkClick(LinkClickCreate):
    """Link click schema"""
    id: int
    bot_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class UTMStats(BaseModel):
    """UTM statistics schema"""
    source: str
    campaign: str
    medium: str
    clicks: int
    unique_users: int
    conversions: int
    conversion_rate: float


class DailyStats(BaseModel):
    """Daily statistics schema"""
    date: date
    total_subscribers: int
    new_subscribers: int
    unsubscribed: int
    active_subscribers: int
    messages_sent: int
    broadcasts_sent: int
    messages_failed: int
    link_clicks: int
    bot_interactions: int
    avg_response_time: Optional[float] = None
    error_rate: float
    engagement_rate: float
    click_through_rate: float


class PeriodStats(BaseModel):
    """Period statistics schema"""
    start_date: date
    end_date: date
    total_subscribers: int
    new_subscribers: int
    unsubscribed: int
    net_growth: int
    growth_rate: float
    messages_sent: int
    broadcasts_sent: int
    link_clicks: int
    avg_engagement_rate: float
    avg_click_through_rate: float
    top_utm_sources: List[UTMStats]
    daily_stats: List[DailyStats]


class TopLink(BaseModel):
    """Top clicked link schema"""
    url: str
    clicks: int
    unique_users: int
    utm_campaign: Optional[str] = None


class EngagementMetrics(BaseModel):
    """Engagement metrics schema"""
    total_users: int
    active_users: int
    engagement_rate: float
    avg_session_duration: Optional[float] = None
    bounce_rate: float
    return_users: int
    return_rate: float


class ConversionFunnel(BaseModel):
    """Conversion funnel schema"""
    step_name: str
    users_entered: int
    users_completed: int
    completion_rate: float


class AnalyticsDashboard(BaseModel):
    """Analytics dashboard data schema"""
    # Overview metrics
    total_subscribers: int
    active_subscribers: int
    new_subscribers_today: int
    messages_sent_today: int
    link_clicks_today: int
    
    # Growth metrics
    subscriber_growth_rate: float
    engagement_growth_rate: float
    
    # Performance metrics
    avg_response_time: float
    error_rate: float
    uptime_percentage: float
    
    # Top content
    top_links: List[TopLink]
    top_utm_campaigns: List[UTMStats]
    
    # Recent activity
    recent_stats: List[DailyStats]
    
    # Engagement
    engagement_metrics: EngagementMetrics
    
    # Conversion funnel
    conversion_funnel: List[ConversionFunnel]


class ReportRequest(BaseModel):
    """Analytics report request schema"""
    start_date: date
    end_date: date
    metrics: List[str]  # List of metric names to include
    group_by: Optional[str] = "day"  # day, week, month
    filters: Optional[Dict[str, Any]] = None
    format: str = "json"  # json, csv, excel


class ExportRequest(BaseModel):
    """Data export request schema"""
    data_type: str  # subscribers, messages, analytics, etc.
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    format: str = "csv"  # csv, excel, json
    include_utm: bool = True
    filters: Optional[Dict[str, Any]] = None
