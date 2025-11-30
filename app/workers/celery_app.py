from celery import Celery

celery_app = Celery(
    "multiav",
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1',
)

celery_app.autodiscover_tasks(["app.workers"])

