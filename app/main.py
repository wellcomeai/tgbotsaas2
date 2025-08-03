"""
FastAPI Main Application - основное приложение
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.exceptions import BotFactoryException
from app.telegram.bot_manager import bot_manager
from app.api.v1 import auth, bots, analytics, health

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    try:
        logger.info("🚀 Starting Bot Factory application...")
        
        # Initialize database
        logger.info("📋 Initializing database...")
        await init_db()
        
        # Initialize and start bot manager
        logger.info("🤖 Starting bot manager...")
        await bot_manager.initialize()
        
        # Start bot manager in background
        bot_task = asyncio.create_task(bot_manager.start())
        
        logger.info("✅ Bot Factory started successfully!")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Failed to start application: {e}")
        raise
    finally:
        # Cleanup
        logger.info("🛑 Shutting down Bot Factory...")
        
        # Stop bot manager
        await bot_manager.stop()
        
        # Close database
        await close_db()
        
        logger.info("✅ Bot Factory shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS
    )


# Exception handlers
@app.exception_handler(BotFactoryException)
async def bot_factory_exception_handler(request: Request, exc: BotFactoryException):
    """Handle custom Bot Factory exceptions"""
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.message,
            "error_code": exc.error_code,
            "type": "BotFactoryError"
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    if settings.DEBUG:
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "type": "InternalServerError"
            }
        )
    else:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "type": "InternalServerError"
            }
        )


# Include API routers
app.include_router(
    health.router,
    prefix=settings.API_V1_PREFIX,
    tags=["health"]
)

app.include_router(
    auth.router,
    prefix=settings.API_V1_PREFIX,
    tags=["auth"]
)

app.include_router(
    bots.router,
    prefix=settings.API_V1_PREFIX,
    tags=["bots"]
)

app.include_router(
    analytics.router,
    prefix=settings.API_V1_PREFIX,
    tags=["analytics"]
)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Bot Factory API",
        "version": settings.VERSION,
        "docs": "/docs",
        "status": "running",
        "bot_manager": {
            "running": bot_manager.is_running,
            "total_bots": len(bot_manager.bot_instances),
            "master_bot_running": bot_manager.application is not None
        }
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check bot manager status
        bot_manager_status = {
            "running": bot_manager.is_running,
            "total_bots": len(bot_manager.bot_instances),
            "master_bot_running": bot_manager.application is not None and bot_manager.application.running
        }
        
        # Check database connection
        from app.core.database import engine
        try:
            async with engine.begin() as conn:
                await conn.execute("SELECT 1")
            database_status = "healthy"
        except Exception as e:
            database_status = f"unhealthy: {str(e)}"
        
        # Overall status
        overall_status = "healthy" if (
            bot_manager.is_running and 
            database_status == "healthy"
        ) else "unhealthy"
        
        return {
            "status": overall_status,
            "timestamp": "2024-01-01T00:00:00Z",  # Would use actual timestamp
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "database": database_status,
            "bot_manager": bot_manager_status,
            "api": "healthy"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": "2024-01-01T00:00:00Z"
            }
        )


# Debug endpoints (only in development)
if settings.DEBUG:
    @app.get("/debug/bot-manager")
    async def debug_bot_manager():
        """Debug bot manager state"""
        return {
            "is_running": bot_manager.is_running,
            "bot_instances": {
                bot_id: {
                    "bot_username": instance.bot_username,
                    "owner_id": instance.owner_id,
                    "status": instance.status,
                    "created_at": instance.created_at.isoformat(),
                    "last_ping": instance.last_ping.isoformat()
                }
                for bot_id, instance in bot_manager.bot_instances.items()
            },
            "token_mapping": bot_manager.token_to_bot_id,
            "username_mapping": bot_manager.username_to_bot_id,
            "stats": bot_manager.get_stats()
        }
    
    @app.post("/debug/restart-bot/{bot_id}")
    async def debug_restart_bot(bot_id: int):
        """Debug endpoint to restart specific bot"""
        try:
            success = await bot_manager.restart_bot(bot_id)
            return {
                "success": success,
                "message": f"Bot {bot_id} restart {'successful' if success else 'failed'}"
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    @app.get("/debug/config")
    async def debug_config():
        """Debug configuration"""
        return {
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "database_url": str(settings.DATABASE_URL),
            "master_bot_token_set": bool(settings.MASTER_BOT_TOKEN),
            "cors_origins": settings.BACKEND_CORS_ORIGINS,
            "api_prefix": settings.API_V1_PREFIX
        }


# Development server
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=settings.DEBUG
    )
