from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "multiav",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL.replace('/0', '/1'),
)

celery_app.autodiscover_tasks(["app.workers"])
