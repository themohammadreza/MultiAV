from app.workers.celery_app import celery_app
from app.services.engines.dispatcher import run_all_engines


@celery_app.task
def run_scan(job_id: str, file_path: str):
    run_all_engines(job_id, file_path)

