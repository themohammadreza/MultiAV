import logging
import time
from typing import List

from celery import chord
from celery.exceptions import SoftTimeLimitExceeded

from app.workers.celery_app import celery
from app.services.orchestrator import dispatcher
from app.services.orchestrator.registry import DEFAULT_ENGINE_TIMEOUT, get_active_engines
from app.services.storage import get_storage_service

logger = logging.getLogger(__name__)

# Provide a small grace window to let tasks handle soft timeouts cleanly.
TIME_LIMIT_GRACE_SECONDS = 5
PERSISTENCE_RETRIES = 3
PERSISTENCE_RETRY_DELAY = 2


@celery.task(bind=True)
def run_engine_task(self, job_id: str, file_path: str, engine_name: str, timeout: int) -> dict:
    """Execute a single AV engine in isolation and persist its result."""
    engine_registry = get_active_engines()
    definition = engine_registry.get(engine_name)

    if not definition:
        message = "Engine is not configured or has been disabled"
        dispatcher.record_engine_result(job_id, engine_name, "error", {"error": message})
        logger.error("Job %s: %s", job_id, message)
        return {"job_id": job_id, "engine": engine_name, "status": "error", "error": message}

    runner = definition["runner"]
    storage = get_storage_service()
    status = "success"

    file_on_disk = file_path
    if not file_on_disk:
        dispatcher.record_dispatch_error(job_id, "Engine task missing file location")
        return {"job_id": job_id, "engine": engine_name, "status": "error"}

    try:
        local_path, cleanup = storage.ensure_local_copy(file_on_disk)
        try:
            payload = runner(local_path)
        finally:
            cleanup()
    except SoftTimeLimitExceeded:
        status = "timeout"
        payload = {
            "error": f"Engine exceeded soft time limit ({timeout}s)",
            "timeout_seconds": timeout,
        }
        logger.warning("Job %s engine %s timed out after %ss", job_id, engine_name, timeout)
    except Exception as exc:  # noqa: BLE001 - ensure task always returns to allow fan-in
        status = "error"
        payload = {"error": str(exc)}
        logger.exception("Job %s engine %s failed: %s", job_id, engine_name, exc)

    # Persist with small in-task retry to avoid re-running the engine on transient DB issues.
    persisted = False
    for attempt in range(1, PERSISTENCE_RETRIES + 1):
        try:
            persisted = dispatcher.record_engine_result(job_id, engine_name, status, payload)
            if persisted:
                break
            raise RuntimeError("record_engine_result returned False")
        except Exception as exc:  # noqa: BLE001 - persistence safeguard
            if attempt == PERSISTENCE_RETRIES:
                logger.exception(
                    "Job %s engine %s failed to persist result after %s attempts: %s",
                    job_id,
                    engine_name,
                    attempt,
                    exc,
                )
            else:
                logger.warning(
                    "Job %s engine %s persistence attempt %s/%s failed: %s",
                    job_id,
                    engine_name,
                    attempt,
                    PERSISTENCE_RETRIES,
                    exc,
                )
                time.sleep(PERSISTENCE_RETRY_DELAY)

    if not persisted:
        dispatcher.record_dispatch_error(job_id, f"Failed to persist engine result for {engine_name}")

    return {"job_id": job_id, "engine": engine_name, "status": status}


@celery.task
def handle_chord_failure(request=None, exc=None, traceback=None, job_id: str = None, **kwargs) -> dict:
    """Mark job as failed if the chord orchestration itself fails."""
    request_id = getattr(request, "id", None) or getattr(request, "task_id", None) or request
    message = f"Chord failure for job {job_id or 'unknown'} (request {request_id}): {exc or 'unknown error'}"
    if job_id:
        dispatcher.record_dispatch_error(job_id, message)
    else:
        logger.error(message)
    return {"job_id": job_id, "status": "error", "error": str(exc or message)}


@celery.task
def finalize_job(engine_task_results: List[dict], job_id: str) -> dict:
    """Fan-in callback: mark job complete and return aggregate summary."""
    summary = dispatcher.finalize_job_summary(job_id)
    if summary is None:
        message = "Job missing during finalize"
        dispatcher.record_dispatch_error(job_id, message)
        return {"job_id": job_id, "status": "error", "error": message}
    return summary


@celery.task
def run_scan(job_id: str, file_location: str, file_path: str | None = None):
    """Orchestrate a scan by fan-out to engine tasks and fan-in aggregation."""
    job = dispatcher.mark_job_status(job_id, "running...")
    if not job:
        message = "Job not found when starting scan"
        dispatcher.record_dispatch_error(job_id, message)
        return {"job_id": job_id, "status": "error", "error": message}

    engine_registry = get_active_engines()
    if not engine_registry:
        dispatcher.record_dispatch_error(job_id, "No engines configured or enabled")
        return {"job_id": job_id, "status": "error", "error": "no_engines"}

    engine_tasks = []
    file_on_disk = file_path or file_location

    for name, definition in engine_registry.items():
        timeout = int(definition.get("timeout", DEFAULT_ENGINE_TIMEOUT) or DEFAULT_ENGINE_TIMEOUT)
        sig = run_engine_task.s(job_id=job_id, file_path=file_location, engine_name=name, timeout=timeout)
        sig = sig.set(soft_time_limit=timeout, time_limit=timeout + TIME_LIMIT_GRACE_SECONDS)
        engine_tasks.append(sig)

    callback = finalize_job.s(job_id=job_id).set(
        link_error=handle_chord_failure.s(job_id=job_id)
    )
    try:
        chord_sig = chord(engine_tasks, callback)
        result = chord_sig.apply_async()
        return {"job_id": job_id, "chord_id": result.id}
    except Exception as exc:  # noqa: BLE001 - ensure the job does not hang in running state
        dispatcher.record_dispatch_error(job_id, f"Failed to enqueue chord: {exc}")
        return {"job_id": job_id, "status": "error", "error": str(exc)}
