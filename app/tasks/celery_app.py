"""Celery application and periodic-task (beat) schedule.

Run a worker:        celery -A app.tasks.celery_app.celery_app worker -l info
Run the scheduler:   celery -A app.tasks.celery_app.celery_app beat -l info

The beat schedule triggers the cleanup task hourly; the task itself deletes any
account that has stayed unverified longer than ``UNVERIFIED_ACCOUNT_TTL_HOURS``
(48h / 2 days by default).
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "users_api",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.cleanup"],
)

celery_app.conf.update(
    task_track_started=True,
    task_time_limit=300,
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "purge-unverified-accounts": {
            "task": "app.tasks.cleanup.purge_unverified_accounts",
            # Run at the top of every hour. A shorter interval would purge more
            # promptly; hourly keeps broker traffic low while staying well
            # within the 2-day SLA.
            "schedule": crontab(minute=0),
        },
    },
)
