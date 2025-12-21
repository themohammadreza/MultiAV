import logging
import os

from celery import Celery
from celery.signals import worker_ready

try:
    from app.core.config import settings
    BROKER_URL = getattr(settings, "CELERY_BROKER_URL", os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"))
    RESULT_BACKEND = getattr(settings, "CELERY_RESULT_BACKEND", os.environ.get("CELERY_RESULT_BACKEND", BROKER_URL))
except Exception:
    BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", BROKER_URL)

from app.services.orchestrator.registry import warm_up_active_engines

logger = logging.getLogger(__name__)

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


@worker_ready.connect
def warm_up_engines_on_worker_ready(**_: object) -> None:
    """Ensure expensive engine initialization (e.g., YARA compile) runs when workers boot."""
    warm_ups = warm_up_active_engines()
    failed = [name for name, ok in warm_ups.items() if not ok]
    if failed:
        logger.warning("Engine warm-up failed for: %s", ", ".join(sorted(failed)))


def create_celery_app():
    """Return the configured Celery instance"""
    return celery
