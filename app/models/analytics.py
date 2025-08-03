"""
Analytics Models - модели аналитики и статистики
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, BigInteger, JSON, DateTime, Float
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Analytics(BaseModel):
    """Analytics event"""
    
    __tablename__ = "analytics"
    
    # Bot
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    
    # User
    user_id = Column(BigInteger, nullable=True, index=True)
    
    # Event details
    event_type = Column(String(100), nullable=False, index=True)
    event_data = Column(JSON, nullable=True)
    
    # Metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # UTM tracking
    utm_source = Column(String(255), nullable=True)
    utm_campaign = Column(String(255), nullable=True)
    utm_medium = Column(String(255), nullable=True)
    utm_content = Column(String(255), nullable=True)
    utm_term = Column(String(255), nullable=True)
    
    # Relationships
    bot = relationship("Bot", back_populates="analytics")
    
    def __repr__(self):
        return f"<Analytics(id={self.id}, event_type={self.event_type}, bot_id={self.bot_id})>"


class LinkClick(BaseModel):
    """Link click tracking"""
    
    __tablename__ = "link_clicks"
    
    # Bot
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    
    # User
    user_id = Column(BigInteger, nullable=False, index=True)
    
    # Link details
    original_url = Column(Text, nullable=False)
    tracked_url = Column(Text, nullable=True)
    
    # UTM parameters
    utm_source = Column(String(255), nullable=True)
    utm_campaign = Column(String(255), nullable=True)
    utm_medium = Column(String(255), nullable=True)
    utm_content = Column(String(255), nullable=True)
    utm_term = Column(String(255), nullable=True)
    
    # Metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    referrer = Column(Text, nullable=True)
    
    # Relationships
    bot = relationship("Bot")
    
    def __repr__(self):
        return f"<LinkClick(id={self.id}, user_id={self.user_id}, bot_id={self.bot_id})>"


class BotStats(BaseModel):
    """Daily bot statistics snapshot"""
    
    __tablename__ = "bot_stats"
    
    # Bot
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    
    # Date
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Subscriber metrics
    total_subscribers = Column(Integer, default=0, nullable=False)
    new_subscribers = Column(Integer, default=0, nullable=False)
    unsubscribed = Column(Integer, default=0, nullable=False)
    active_subscribers = Column(Integer, default=0, nullable=False)
    
    # Message metrics
    messages_sent = Column(Integer, default=0, nullable=False)
    broadcasts_sent = Column(Integer, default=0, nullable=False)
    messages_failed = Column(Integer, default=0, nullable=False)
    
    # Engagement metrics
    link_clicks = Column(Integer, default=0, nullable=False)
    bot_interactions = Column(Integer, default=0, nullable=False)
    
    # Performance metrics
    avg_response_time = Column(Float, nullable=True)
    error_rate = Column(Float, default=0.0, nullable=False)
    
    # Relationships
    bot = relationship("Bot")
    
    def __repr__(self):
        return f"<BotStats(bot_id={self.bot_id}, date={self.date})>"
    
    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate"""
        if self.total_subscribers == 0:
            return 0.0
        return (self.bot_interactions / self.total_subscribers) * 100
    
    @property
    def click_through_rate(self) -> float:
        """Calculate click-through rate"""
        if self.messages_sent == 0:
            return 0.0
        return (self.link_clicks / self.messages_sent) * 100


class UTMCampaign(BaseModel):
    """UTM campaign tracking"""
    
    __tablename__ = "utm_campaigns"
    
    # Bot
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    
    # Campaign details
    name = Column(String(255), nullable=False)
    utm_source = Column(String(255), nullable=False)
    utm_campaign = Column(String(255), nullable=False)
    utm_medium = Column(String(255), nullable=False)
    utm_content = Column(String(255), nullable=True)
    utm_term = Column(String(255), nullable=True)
    
    # Statistics
    total_clicks = Column(Integer, default=0, nullable=False)
    unique_clicks = Column(Integer, default=0, nullable=False)
    conversions = Column(Integer, default=0, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    bot = relationship("Bot")
    
    def __repr__(self):
        return f"<UTMCampaign(id={self.id}, name={self.name})>"
    
    @property
    def conversion_rate(self) -> float:
        """Calculate conversion rate"""
        if self.unique_clicks == 0:
            return 0.0
        return (self.conversions / self.unique_clicks) * 100
