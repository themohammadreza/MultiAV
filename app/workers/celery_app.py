from celery import Celery
import os

try:
    from app.core.config import settings
    BROKER_URL = getattr(settings, "CELERY_BROKER_URL", os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"))
    RESULT_BACKEND = getattr(settings, "CELERY_RESULT_BACKEND", os.environ.get("CELERY_RESULT_BACKEND", BROKER_URL))
except Exception:
    BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", BROKER_URL)

celery = Celery("multiav", broker=BROKER_URL, backend=RESULT_BACKEND)

celery.conf.update(
    result_backend=RESULT_BACKEND,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_default_queue="celery",
)

from app.workers import tasks

def create_celery_app():
    """Return the configured Celery instance"""
    return celery
