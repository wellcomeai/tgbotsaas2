"""
Database migration script
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add app to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic.config import Config
from alembic import command
from app.core.database import engine
from app.models import *  # Import all models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migrations():
    """Run Alembic migrations"""
    try:
        logger.info("🔄 Running database migrations...")
        
        # Create Alembic config
        alembic_cfg = Config("alembic.ini")
        
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        
        logger.info("✅ Migrations completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_migrations())
