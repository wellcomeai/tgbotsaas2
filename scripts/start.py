"""
Production startup script for Render
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add app to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_configuration():
    """Check configuration before starting"""
    try:
        from app.core.config import settings
        
        logger.info("🔍 Checking configuration...")
        
        # Test critical settings
        assert settings.SECRET_KEY, "SECRET_KEY is required"
        assert settings.MASTER_BOT_TOKEN, "MASTER_BOT_TOKEN is required"
        assert settings.DATABASE_URL, "DATABASE_URL is required"
        
        logger.info("✅ Configuration check passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Configuration check failed: {e}")
        return False


async def startup_sequence():
    """Initialize all services before starting"""
    try:
        logger.info("🔄 Starting Bot Factory initialization...")
        
        # Check configuration first
        if not check_configuration():
            logger.error("Configuration check failed, aborting startup")
            sys.exit(1)
        
        # Initialize database
        logger.info("📋 Initializing database...")
        from app.core.database import init_db
        await init_db()
        
        # Initialize bot manager
        logger.info("🤖 Initializing bot manager...")
        from app.telegram.bot_manager import bot_manager
        await bot_manager.initialize()
        
        logger.info("✅ Bot Factory initialization complete!")
        
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        raise


if __name__ == "__main__":
    try:
        # Run startup sequence
        asyncio.run(startup_sequence())
        
        # Start the application
        import uvicorn
        
        port = int(os.getenv("PORT", 8000))
        host = "0.0.0.0"
        
        logger.info(f"🚀 Starting server on {host}:{port}")
        
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        sys.exit(1)
