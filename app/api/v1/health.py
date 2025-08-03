"""
Health Check Endpoints - проверка состояния системы
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, engine
from app.telegram.bot_manager import bot_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Bot Factory API",
        "version": "2.0.0"
    }


@router.get("/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Detailed health check with all components"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    overall_healthy = True
    
    # Database check
    try:
        await db.execute("SELECT 1")
        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy", 
            "message": f"Database error: {str(e)}"
        }
        overall_healthy = False
    
    # Bot Manager check
    try:
        bot_manager_healthy = bot_manager.is_running
        active_bots = len(bot_manager.bot_instances)
        
        health_status["checks"]["bot_manager"] = {
            "status": "healthy" if bot_manager_healthy else "unhealthy",
            "message": f"Bot manager running: {bot_manager_healthy}",
            "active_bots": active_bots,
            "master_bot_running": bot_manager.application is not None
        }
        
        if not bot_manager_healthy:
            overall_healthy = False
            
    except Exception as e:
        health_status["checks"]["bot_manager"] = {
            "status": "unhealthy",
            "message": f"Bot manager error: {str(e)}"
        }
        overall_healthy = False
    
    # Memory check (basic)
    try:
        import psutil
        memory = psutil.virtual_memory()
        
        health_status["checks"]["memory"] = {
            "status": "healthy" if memory.percent < 90 else "warning",
            "usage_percent": memory.percent,
            "available_mb": memory.available // 1024 // 1024
        }
    except ImportError:
        health_status["checks"]["memory"] = {
            "status": "unknown",
            "message": "psutil not available"
        }
    except Exception as e:
        health_status["checks"]["memory"] = {
            "status": "error",
            "message": str(e)
        }
    
    # Set overall status
    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    
    if not overall_healthy:
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness check for Kubernetes/Docker"""
    try:
        # Check database
        await db.execute("SELECT 1")
        
        # Check bot manager is initialized
        if not bot_manager.application:
            raise HTTPException(
                status_code=503, 
                detail="Bot manager not initialized"
            )
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}"
        )


@router.get("/live")
async def liveness_check():
    """Liveness check for Kubernetes/Docker"""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/metrics")
async def get_metrics():
    """Basic metrics endpoint"""
    try:
        bot_stats = bot_manager.get_stats() if bot_manager else {}
        
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "bot_manager": bot_stats,
            "uptime_seconds": bot_stats.get("uptime", 0)
        }
        
        # Add memory info if available
        try:
            import psutil
            process = psutil.Process()
            metrics["memory"] = {
                "rss_mb": process.memory_info().rss // 1024 // 1024,
                "percent": process.memory_percent()
            }
            metrics["cpu_percent"] = process.cpu_percent()
        except ImportError:
            pass
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get metrics")
