"""
Message Models - модели сообщений и рассылок
"""

from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, BigInteger, JSON, DateTime
from sqlalchemy.orm import relationship
from enum import Enum
from app.models.base import BaseModel


class MessageType(str, Enum):
    """Message type enumeration"""
    WELCOME = "welcome"
    FAREWELL = "farewell"
    BROADCAST = "broadcast"
    AUTO_APPROVAL = "auto_approval"
    SCHEDULED = "scheduled"
    ADMIN = "admin"


class MessageStatus(str, Enum):
    """Message status enumeration"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Message(BaseModel):
    """Message sent by bot"""
    
    __tablename__ = "messages"
    
    # Bot
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    
    # Recipient
    recipient_id = Column(BigInteger, nullable=True, index=True)  # Telegram user ID
    
    # Message content
    message_type = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    
    # Status
    status = Column(String(50), default=MessageStatus.SENT.value, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    
    # UTM tracking
    utm_source = Column(String(255), nullable=True)
    utm_campaign = Column(String(255), nullable=True)
    utm_medium = Column(String(255), nullable=True)
    utm_content = Column(String(255), nullable=True)
    
    # Metadata
    telegram_message_id = Column(BigInteger, nullable=True)
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    sent_at = Column(DateTime(timezone=True), nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    bot = relationship("Bot", back_populates="messages")
    
    def __repr__(self):
        return f"<Message(id={self.id}, bot_id={self.bot_id}, type={self.message_type})>"


class Broadcast(BaseModel):
    """Broadcast campaign"""
    
    __tablename__ = "broadcasts"
    
    # Bot
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    
    # Campaign details
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    
    # Media
    photo_url = Column(String(500), nullable=True)
    document_url = Column(String(500), nullable=True)
    
    # Status
    status = Column(String(50), default=MessageStatus.DRAFT.value, nullable=False, index=True)
    
    # Statistics
    total_recipients = Column(Integer, default=0, nullable=False)
    successful_sends = Column(Integer, default=0, nullable=False)
    failed_sends = Column(Integer, default=0, nullable=False)
    
    # UTM tracking
    utm_source = Column(String(255), nullable=True)
    utm_campaign = Column(String(255), nullable=True)
    utm_medium = Column(String(255), nullable=True)
    
    # Scheduling
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Configuration
    target_audience = Column(JSON, nullable=True)  # Filters for targeting
    send_delay = Column(Integer, default=1, nullable=False)  # Seconds between messages
    
    # Relationships
    bot = relationship("Bot")
    
    def __repr__(self):
        return f"<Broadcast(id={self.id}, title={self.title}, status={self.status})>"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_recipients == 0:
            return 0.0
        return (self.successful_sends / self.total_recipients) * 100
    
    @property
    def is_completed(self) -> bool:
        """Check if broadcast is completed"""
        return self.status in [MessageStatus.SENT.value, MessageStatus.FAILED.value, MessageStatus.CANCELLED.value]


class BroadcastButton(BaseModel):
    """Broadcast inline button"""
    
    __tablename__ = "broadcast_buttons"
    
    # Broadcast
    broadcast_id = Column(Integer, ForeignKey("broadcasts.id"), nullable=False, index=True)
    
    # Button details
    text = Column(String(255), nullable=False)
    url = Column(String(500), nullable=True)
    callback_data = Column(String(255), nullable=True)
    
    # Position
    row = Column(Integer, default=0, nullable=False)
    column = Column(Integer, default=0, nullable=False)
    
    # Relationships
    broadcast = relationship("Broadcast")
    
    def __repr__(self):
        return f"<BroadcastButton(id={self.id}, text={self.text})>"
