"""
API v1 - Version 1 endpoints
"""

from fastapi import APIRouter
from app.api.v1 import auth, bots, analytics, health

api_router = APIRouter()

# Include all v1 routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(bots.router, prefix="/bots", tags=["bots"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])

__all__ = ["api_router"]
