"""
User Schemas - Pydantic схемы для пользователей
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, validator
from app.models.user import User as UserModel


class UserBase(BaseModel):
    """Base user schema"""
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: str = "ru"
    timezone: str = "UTC"


class UserCreate(UserBase):
    """Schema for creating user"""
    pass


class UserUpdate(BaseModel):
    """Schema for updating user"""
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class UserInDB(UserBase):
    """User schema with database fields"""
    id: int
    is_active: bool
    is_premium: bool
    subscription_type: str
    subscription_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class User(UserInDB):
    """Public user schema"""
    display_name: str
    is_subscription_active: bool
    
    @validator("display_name", pre=True, always=True)
    def set_display_name(cls, v, values):
        if v:
            return v
        # Calculate display name from other fields
        first_name = values.get("first_name")
        last_name = values.get("last_name")
        username = values.get("username")
        telegram_id = values.get("telegram_id")
        
        if first_name and last_name:
            return f"{first_name} {last_name}"
        elif first_name:
            return first_name
        elif username:
            return f"@{username}"
        else:
            return f"User {telegram_id}"
    
    @validator("is_subscription_active", pre=True, always=True)
    def set_subscription_active(cls, v, values):
        if v is not None:
            return v
        # Calculate subscription status
        subscription_type = values.get("subscription_type")
        subscription_expires_at = values.get("subscription_expires_at")
        
        if subscription_type == "free":
            return True
        if subscription_expires_at:
            return datetime.utcnow() < subscription_expires_at
        return False


class UserStats(BaseModel):
    """User statistics schema"""
    total_bots: int
    active_bots: int
    total_subscribers: int
    messages_sent: int
    link_clicks: int
    
    class Config:
        from_attributes = True


class UserWithStats(User):
    """User with statistics"""
    stats: UserStats
