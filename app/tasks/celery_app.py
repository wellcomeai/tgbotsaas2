"""
Celery Application Configuration
"""

import os
from celery import Celery
from app.core.config import settings

# Create Celery instance
celery_app = Celery(
    "bot_factory",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        'app.tasks.bot_tasks',
        'app.tasks.message_tasks', 
        'app.tasks.analytics_tasks'
    ]
)

# Configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Task routes
celery_app.conf.task_routes = {
    'app.tasks.bot_tasks.*': {'queue': 'bot_operations'},
    'app.tasks.message_tasks.*': {'queue': 'message_processing'},
    'app.tasks.analytics_tasks.*': {'queue': 'analytics'},
}

if __name__ == '__main__':
    celery_app.start()
