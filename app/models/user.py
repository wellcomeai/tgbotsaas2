"""
User Models - модели пользователей
"""

from sqlalchemy import Column, Integer, String, Boolean, BigInteger, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class User(BaseModel):
    """SaaS platform user"""
    
    __tablename__ = "users"
    
    # Telegram data
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_premium = Column(Boolean, default=False, nullable=False)
    
    # Settings
    language_code = Column(String(10), default="ru", nullable=False)
    timezone = Column(String(50), default="UTC", nullable=False)
    
    # Subscription info
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    subscription_type = Column(String(50), default="free", nullable=False)
    
    # Relationships
    bots = relationship("Bot", back_populates="owner", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"
    
    @property
    def display_name(self) -> str:
        """Get user display name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        else:
            return f"User {self.telegram_id}"
    
    @property
    def is_subscription_active(self) -> bool:
        """Check if subscription is active"""
        if self.subscription_type == "free":
            return True
        if self.subscription_expires_at:
            from datetime import datetime
            return datetime.utcnow() < self.subscription_expires_at
        return False
