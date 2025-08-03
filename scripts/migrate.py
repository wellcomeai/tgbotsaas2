"""
Database migration script
"""

import os
import logging
import sys
from pathlib import Path

# Add app to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic.config import Config
from alembic import command

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migrations():
    """Run Alembic migrations"""
    try:
        logger.info("🔄 Running database migrations...")
        
        # Create Alembic config
        alembic_cfg = Config("alembic.ini")
        
        # Set database URL from environment if available
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # Convert postgres:// to postgresql+asyncpg:// if needed
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
            alembic_cfg.set_main_option("sqlalchemy.url", database_url)
        
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        
        logger.info("✅ Migrations completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migrations()
