import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import EngineResult, ScanJob
from app.db.session import SessionLocal
from app.services.aggregator.summary import summarize_job
from app.services.orchestrator.registry import get_active_engines

logger = logging.getLogger(__name__)


def _get_job(db: Session, job_id: str) -> Optional[ScanJob]:
    """Fetch a ScanJob by id without leaking session management."""
    return db.query(ScanJob).filter(ScanJob.id == job_id).first()


def mark_job_status(job_id: str, status: str, *, completed: bool = False) -> Optional[ScanJob]:
    """Update a job's status (and optionally completion timestamp)."""
    db = SessionLocal()
    try:
        job = _get_job(db, job_id)
        if not job:
            logger.warning("Job %s not found while setting status to %s", job_id, status)
            return None

        job.status = status
        if completed:
            job.completed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def record_engine_result(job_id: str, engine: str, status: str, result: Dict) -> bool:
    """Upsert a single EngineResult per (job, engine) to keep results unique.

    Returns True on success, False if persistence failed or job was missing.
    """
    db = SessionLocal()
    try:
        payload = result or {}
        payload.setdefault("engine", engine)
        payload.setdefault("status", status)

        job = _get_job(db, job_id)
        if not job:
            logger.warning("Dropping engine result for missing job %s (%s)", job_id, engine)
            return False

        def _apply_update(target: EngineResult) -> None:
            target.status = status
            target.result = payload
            target.scanned_at = datetime.now(timezone.utc)

        existing = (
            db.query(EngineResult)
            .filter(EngineResult.job_id == job_id, EngineResult.engine == engine)
            .first()
        )

        if existing:
            _apply_update(existing)
            db.commit()
            return True

        try:
            db.add(
                EngineResult(
                    job_id=job_id,
                    engine=engine,
                    status=status,
                    result=payload,
                )
            )
            db.commit()
            return True
        except IntegrityError:
            # Another worker inserted concurrently; refresh and update.
            db.rollback()
            existing = (
                db.query(EngineResult)
                .filter(EngineResult.job_id == job_id, EngineResult.engine == engine)
                .first()
            )
            if existing:
                _apply_update(existing)
                db.commit()
                return True
            logger.exception(
                "IntegrityError persisting engine result for job %s engine %s", job_id, engine
            )
            return False
    finally:
        db.close()


def record_dispatch_error(job_id: str, message: str) -> None:
    """Persist an orchestrator-level error for observability and debugging."""
    logger.error("Dispatcher error for job %s: %s", job_id, message)
    record_engine_result(job_id, "Orchestrator", "error", {"error": message})
    mark_job_status(job_id, "error", completed=True)


def finalize_job_summary(job_id: str) -> Optional[dict]:
    """Mark job completion and return an aggregated summary."""
    db = SessionLocal()
    try:
        job = _get_job(db, job_id)
        if not job:
            logger.warning("Attempted to finalize missing job %s", job_id)
            return None

        engine_results = sorted(job.results, key=lambda r: r.scanned_at or job.created_at)
        success_count = sum(1 for r in engine_results if r.status == "success")
        error_count = sum(1 for r in engine_results if r.status != "success")

        if not engine_results:
            job.status = "error"
        elif success_count == 0 and error_count > 0:
            job.status = "error"
        elif error_count > 0:
            job.status = "done_with_errors"
        else:
            job.status = "done"

        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)

        return summarize_job(job, engine_results)
    finally:
        db.close()


def load_engine_registry() -> Dict:
    """Expose active engine registry for callers that cannot import registry directly."""
    return get_active_engines()


def run_all_engines(job_id: str, file_path: str):
    """Compatibility shim: enqueue the Celery-based orchestration."""
    try:
        # Local import to avoid circular dependency during module load
        from app.workers.tasks import run_scan
    except Exception as exc:  # noqa: BLE001 - best-effort compatibility
        logger.error("Unable to enqueue job %s: %s", job_id, exc)
        return None

    return run_scan.delay(str(job_id), file_path)
