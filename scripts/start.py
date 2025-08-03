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

from app.main import app
from app.core.database import init_db
from app.telegram.bot_manager import bot_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def startup_sequence():
    """Initialize all services before starting"""
    try:
        logger.info("🔄 Starting Bot Factory initialization...")
        
        # Initialize database
        logger.info("📋 Initializing database...")
        await init_db()
        
        # Initialize bot manager
        logger.info("🤖 Initializing bot manager...")
        await bot_manager.initialize()
        
        logger.info("✅ Bot Factory initialization complete!")
        
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        raise


if __name__ == "__main__":
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
