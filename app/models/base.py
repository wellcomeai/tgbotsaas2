"""
Base Models - базовые модели для наследования
"""

from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.ext.declarative import declared_attr
from app.core.database import Base


class TimestampMixin:
    """Mixin для добавления timestamp полей"""
    
    @declared_attr
    def created_at(cls):
        return Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False
        )


class BaseModel(Base, TimestampMixin):
    """Base model with common fields"""
    
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True)
    
    def dict(self):
        """Convert model to dict"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
