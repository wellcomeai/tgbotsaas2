"""
Core Configuration - централизованная конфигурация приложения
"""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Telegram Bot Factory"
    VERSION: str = "2.0.0"
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database - сделаем поля опциональными если есть DATABASE_URL
    POSTGRES_SERVER: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_PORT: str = "5432"
    DATABASE_URL: Optional[PostgresDsn] = None
    
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info) -> str:
        if isinstance(v, str):
            # Конвертируем postgres:// или postgresql:// в postgresql+asyncpg://
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif not v.startswith("postgresql+asyncpg://"):
                # Если схема другая, добавляем asyncpg
                if "://" in v:
                    scheme, rest = v.split("://", 1)
                    v = f"postgresql+asyncpg://{rest}"
            
            return v
        
        values = info.data if hasattr(info, 'data') else {}
        
        # Если DATABASE_URL не предоставлен, собираем из отдельных компонентов
        if not v:
            server = values.get("POSTGRES_SERVER")
            user = values.get("POSTGRES_USER")
            password = values.get("POSTGRES_PASSWORD")
            db = values.get("POSTGRES_DB")
            port = values.get("POSTGRES_PORT", "5432")
            
            if all([server, user, password, db]):
                return PostgresDsn.build(
                    scheme="postgresql+asyncpg",
                    username=user,
                    password=password,
                    host=server,
                    port=port,
                    path=f"/{db}",
                )
            else:
                raise ValueError("Either DATABASE_URL or all POSTGRES_* variables must be provided")
        
        return v
    
    # Redis (optional)
    REDIS_URL: Optional[str] = None
    USE_REDIS: bool = False
    
    # Telegram
    MASTER_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_URL: Optional[str] = None
    USE_WEBHOOKS: bool = False
    
    # Bot Management
    MAX_BOTS_PER_USER: int = 5
    BOT_HEALTH_CHECK_INTERVAL: int = 300  # seconds
    MESSAGE_RATE_LIMIT: int = 30  # per minute
    
    # File Storage
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "https://localhost:3000"]
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # Celery (Background Tasks)
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # Performance
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 30
    
    # Feature Flags
    ENABLE_ANALYTICS: bool = True
    ENABLE_UTM_TRACKING: bool = True
    ENABLE_RATE_LIMITING: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
