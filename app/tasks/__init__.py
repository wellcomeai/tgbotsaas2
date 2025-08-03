"""
Background Tasks with Celery
"""

from app.tasks.celery_app import celery_app
from app.tasks.bot_tasks import *
from app.tasks.message_tasks import *
from app.tasks.analytics_tasks import *

__all__ = ["celery_app"]
