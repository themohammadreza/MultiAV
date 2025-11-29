from celery import Celery

celery_app = Celery(
    "multiav",
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1',
)

celery_app.conf.task_routes = {"app.workers.task.*": {"queue": "scans"}}

