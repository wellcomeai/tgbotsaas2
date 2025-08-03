"""
Message Schemas - Pydantic схемы для сообщений
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, field_validator, HttpUrl
from app.models.message import MessageType, MessageStatus


class MessageBase(BaseModel):
    """Base message schema"""
    content: str
    message_type: MessageType = MessageType.BROADCAST
    utm_source: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_medium: Optional[str] = "telegram"
    utm_content: Optional[str] = None


class MessageCreate(MessageBase):
    """Schema for creating message"""
    recipient_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageUpdate(BaseModel):
    """Schema for updating message"""
    content: Optional[str] = None
    status: Optional[MessageStatus] = None
    scheduled_at: Optional[datetime] = None


class MessageInDB(MessageBase):
    """Message schema with database fields"""
    id: int
    bot_id: int
    recipient_id: Optional[int] = None
    status: MessageStatus
    error_message: Optional[str] = None
    telegram_message_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    sent_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class Message(MessageInDB):
    """Public message schema"""
    is_sent: bool
    is_scheduled: bool
    
    @field_validator("is_sent", mode="before")
    @classmethod
    def set_is_sent(cls, v, info):
        if v is not None:
            return v
        values = info.data if hasattr(info, 'data') else {}
        status = values.get("status")
        return status == MessageStatus.SENT.value
    
    @field_validator("is_scheduled", mode="before")
    @classmethod
    def set_is_scheduled(cls, v, info):
        if v is not None:
            return v
        values = info.data if hasattr(info, 'data') else {}
        scheduled_at = values.get("scheduled_at")
        status = values.get("status")
        return scheduled_at is not None and status == MessageStatus.SCHEDULED.value


class BroadcastButton(BaseModel):
    """Broadcast button schema"""
    text: str
    url: Optional[HttpUrl] = None
    callback_data: Optional[str] = None
    row: int = 0
    column: int = 0
    
    @field_validator("url", "callback_data")
    @classmethod
    def validate_button_action(cls, v, info):
        field_name = info.field_name
        values = info.data if hasattr(info, 'data') else {}
        
        url = values.get("url") if field_name == "callback_data" else v
        callback_data = values.get("callback_data") if field_name == "url" else v
        
        if not url and not callback_data:
            raise ValueError("Button must have either URL or callback_data")
        if url and callback_data:
            raise ValueError("Button cannot have both URL and callback_data")
        return v


class BroadcastBase(BaseModel):
    """Base broadcast schema"""
    title: str
    content: str
    photo_url: Optional[HttpUrl] = None
    document_url: Optional[HttpUrl] = None
    utm_source: Optional[str] = "broadcast"
    utm_campaign: Optional[str] = None
    utm_medium: Optional[str] = "telegram"
    send_delay: int = 1  # seconds
    target_audience: Optional[Dict[str, Any]] = None


class BroadcastCreate(BroadcastBase):
    """Schema for creating broadcast"""
    scheduled_at: Optional[datetime] = None
    buttons: Optional[List[BroadcastButton]] = None


class BroadcastUpdate(BaseModel):
    """Schema for updating broadcast"""
    title: Optional[str] = None
    content: Optional[str] = None
    photo_url: Optional[HttpUrl] = None
    document_url: Optional[HttpUrl] = None
    scheduled_at: Optional[datetime] = None
    target_audience: Optional[Dict[str, Any]] = None
    send_delay: Optional[int] = None
    status: Optional[MessageStatus] = None


class BroadcastInDB(BroadcastBase):
    """Broadcast schema with database fields"""
    id: int
    bot_id: int
    status: MessageStatus
    total_recipients: int
    successful_sends: int
    failed_sends: int
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class Broadcast(BroadcastInDB):
    """Public broadcast schema"""
    success_rate: float
    is_completed: bool
    buttons: Optional[List[BroadcastButton]] = None
    
    @field_validator("success_rate", mode="before")
    @classmethod
    def set_success_rate(cls, v, info):
        if v is not None:
            return v
        values = info.data if hasattr(info, 'data') else {}
        total = values.get("total_recipients", 0)
        successful = values.get("successful_sends", 0)
        return (successful / total * 100) if total > 0 else 0.0
    
    @field_validator("is_completed", mode="before")
    @classmethod
    def set_is_completed(cls, v, info):
        if v is not None:
            return v
        values = info.data if hasattr(info, 'data') else {}
        status = values.get("status")
        return status in [MessageStatus.SENT.value, MessageStatus.FAILED.value, MessageStatus.CANCELLED.value]


class BroadcastStats(BaseModel):
    """Broadcast statistics schema"""
    total_broadcasts: int
    active_broadcasts: int
    scheduled_broadcasts: int
    total_recipients: int
    successful_sends: int
    failed_sends: int
    avg_success_rate: float
    
    class Config:
        from_attributes = True
