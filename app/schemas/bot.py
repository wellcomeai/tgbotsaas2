"""
Bot Schemas - Pydantic схемы для ботов
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, validator, HttpUrl
from app.models.bot import BotStatus


class BotBase(BaseModel):
    """Base bot schema"""
    bot_username: str
    bot_display_name: Optional[str] = None
    channel_id: Optional[int] = None
    channel_username: Optional[str] = None
    auto_approve_requests: bool = True
    welcome_message_enabled: bool = True
    farewell_message_enabled: bool = True
    utm_tracking_enabled: bool = True
    welcome_message: Optional[str] = None
    farewell_message: Optional[str] = None
    auto_approve_message: Optional[str] = None


class BotCreate(BotBase):
    """Schema for creating bot"""
    bot_token: str
    
    @validator("bot_token")
    def validate_bot_token(cls, v):
        if ":" not in v or len(v.split(":")) != 2:
            raise ValueError("Invalid bot token format")
        return v
    
    @validator("bot_username")
    def validate_bot_username(cls, v):
        if not v.endswith("bot"):
            raise ValueError("Bot username must end with 'bot'")
        return v.lower()


class BotUpdate(BaseModel):
    """Schema for updating bot"""
    bot_display_name: Optional[str] = None
    channel_id: Optional[int] = None
    channel_username: Optional[str] = None
    auto_approve_requests: Optional[bool] = None
    welcome_message_enabled: Optional[bool] = None
    farewell_message_enabled: Optional[bool] = None
    utm_tracking_enabled: Optional[bool] = None
    welcome_message: Optional[str] = None
    farewell_message: Optional[str] = None
    auto_approve_message: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class BotInDB(BotBase):
    """Bot schema with database fields"""
    id: int
    owner_id: int
    bot_token: str
    status: BotStatus
    error_message: Optional[str] = None
    last_ping_at: Optional[datetime] = None
    config: Optional[Dict[str, Any]] = None
    total_subscribers: int
    messages_sent: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class Bot(BotInDB):
    """Public bot schema"""
    is_active: bool
    telegram_link: str
    
    @validator("is_active", pre=True, always=True)
    def set_is_active(cls, v, values):
        if v is not None:
            return v
        status = values.get("status")
        return status == BotStatus.ACTIVE.value
    
    @validator("telegram_link", pre=True, always=True)
    def set_telegram_link(cls, v, values):
        if v:
            return v
        username = values.get("bot_username")
        return f"https://t.me/{username}" if username else ""


class BotStats(BaseModel):
    """Bot statistics schema"""
    total_subscribers: int
    active_subscribers: int
    new_subscribers_today: int
    messages_sent_today: int
    messages_sent_total: int
    link_clicks_today: int
    link_clicks_total: int
    engagement_rate: float
    error_rate: float
    uptime_percentage: float
    
    class Config:
        from_attributes = True


class BotWithStats(Bot):
    """Bot with statistics"""
    stats: BotStats


class BotSubscriber(BaseModel):
    """Bot subscriber schema"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    bot_started: bool
    utm_source: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_medium: Optional[str] = None
    last_activity_at: Optional[datetime] = None
    joined_at: datetime
    display_name: str
    
    @validator("display_name", pre=True, always=True)
    def set_display_name(cls, v, values):
        if v:
            return v
        first_name = values.get("first_name")
        last_name = values.get("last_name")
        username = values.get("username")
        user_id = values.get("user_id")
        
        if first_name and last_name:
            return f"{first_name} {last_name}"
        elif first_name:
            return first_name
        elif username:
            return f"@{username}"
        else:
            return f"User {user_id}"
    
    class Config:
        from_attributes = True


class BotConfigUpdate(BaseModel):
    """Schema for updating bot configuration"""
    welcome_message: Optional[str] = None
    farewell_message: Optional[str] = None
    auto_approve_message: Optional[str] = None
    auto_approve_requests: Optional[bool] = None
    welcome_message_enabled: Optional[bool] = None
    farewell_message_enabled: Optional[bool] = None
    utm_tracking_enabled: Optional[bool] = None
    custom_config: Optional[Dict[str, Any]] = None
