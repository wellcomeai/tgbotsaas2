"""
Pydantic Schemas - экспорт всех схем
"""

from app.schemas.user import User, UserCreate, UserUpdate, UserStats, UserWithStats
from app.schemas.bot import (
    Bot, BotCreate, BotUpdate, BotStats, BotWithStats, 
    BotSubscriber, BotConfigUpdate
)
from app.schemas.message import (
    Message, MessageCreate, MessageUpdate, 
    Broadcast, BroadcastCreate, BroadcastUpdate, BroadcastButton,
    BroadcastStats
)
from app.schemas.analytics import (
    AnalyticsEvent, AnalyticsEventInDB, LinkClick, LinkClickCreate,
    DailyStats, PeriodStats, UTMStats, AnalyticsDashboard,
    ReportRequest, ExportRequest
)

__all__ = [
    # User schemas
    "User", "UserCreate", "UserUpdate", "UserStats", "UserWithStats",
    
    # Bot schemas  
    "Bot", "BotCreate", "BotUpdate", "BotStats", "BotWithStats",
    "BotSubscriber", "BotConfigUpdate",
    
    # Message schemas
    "Message", "MessageCreate", "MessageUpdate",
    "Broadcast", "BroadcastCreate", "BroadcastUpdate", "BroadcastButton",
    "BroadcastStats",
    
    # Analytics schemas
    "AnalyticsEvent", "AnalyticsEventInDB", "LinkClick", "LinkClickCreate",
    "DailyStats", "PeriodStats", "UTMStats", "AnalyticsDashboard", 
    "ReportRequest", "ExportRequest"
]
