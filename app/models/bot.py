"""
Bot Models - модели ботов
"""

from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, BigInteger, JSON
from sqlalchemy.orm import relationship
from enum import Enum
from app.models.base import BaseModel


class BotStatus(str, Enum):
    """Bot status enumeration"""
    CREATING = "creating"
    ACTIVE = "active"
    STOPPED = "stopped"
    ERROR = "error"
    DELETED = "deleted"


class Bot(BaseModel):
    """User bot instance"""
    
    __tablename__ = "bots"
    
    # Owner
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Bot details
    bot_token = Column(String(255), unique=True, nullable=False)
    bot_username = Column(String(255), nullable=False, index=True)
    bot_display_name = Column(String(255), nullable=True)
    
    # Channel settings
    channel_id = Column(BigInteger, nullable=True, index=True)
    channel_username = Column(String(255), nullable=True)
    
    # Status
    status = Column(String(50), default=BotStatus.CREATING.value, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    last_ping_at = Column(DateTime(timezone=True), nullable=True)
    
    # Configuration
    config = Column(JSON, nullable=True)
    
    # Settings
    auto_approve_requests = Column(Boolean, default=True, nullable=False)
    welcome_message_enabled = Column(Boolean, default=True, nullable=False)
    farewell_message_enabled = Column(Boolean, default=True, nullable=False)
    utm_tracking_enabled = Column(Boolean, default=True, nullable=False)
    
    # Messages
    welcome_message = Column(Text, nullable=True)
    farewell_message = Column(Text, nullable=True)
    auto_approve_message = Column(Text, nullable=True)
    
    # Statistics
    total_subscribers = Column(Integer, default=0, nullable=False)
    messages_sent = Column(Integer, default=0, nullable=False)
    
    # Relationships
    owner = relationship("User", back_populates="bots")
    messages = relationship("Message", back_populates="bot", cascade="all, delete-orphan")
    analytics = relationship("Analytics", back_populates="bot", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Bot(id={self.id}, username={self.bot_username}, status={self.status})>"
    
    @property
    def is_active(self) -> bool:
        """Check if bot is active"""
        return self.status == BotStatus.ACTIVE.value
    
    @property
    def telegram_link(self) -> str:
        """Get Telegram link to bot"""
        return f"https://t.me/{self.bot_username}"
    
    def get_config_value(self, key: str, default=None):
        """Get configuration value"""
        if not self.config:
            return default
        return self.config.get(key, default)
    
    def set_config_value(self, key: str, value):
        """Set configuration value"""
        if not self.config:
            self.config = {}
        self.config[key] = value


class BotSubscriber(BaseModel):
    """Bot channel subscriber"""
    
    __tablename__ = "bot_subscribers"
    
    # Bot
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    
    # Subscriber info
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    bot_started = Column(Boolean, default=False, nullable=False)
    
    # UTM tracking
    utm_source = Column(String(255), nullable=True)
    utm_campaign = Column(String(255), nullable=True)
    utm_medium = Column(String(255), nullable=True)
    
    # Activity
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    bot = relationship("Bot")
    
    def __repr__(self):
        return f"<BotSubscriber(bot_id={self.bot_id}, user_id={self.user_id})>"
    
    @property
    def display_name(self) -> str:
        """Get subscriber display name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        else:
            return f"User {self.user_id}"
