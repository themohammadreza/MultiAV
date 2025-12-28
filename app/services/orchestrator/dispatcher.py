import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import ApiKeyUsage, EngineResult, ScanJob
from app.db.session import SessionLocal
from app.services.aggregator.summary import summarize_job
from app.services.orchestrator.registry import get_active_engines

logger = logging.getLogger(__name__)


def _normalize_job_id(job_id: str | UUID) -> UUID | None:
    try:
        return job_id if isinstance(job_id, UUID) else UUID(str(job_id))
    except Exception:
        return None


def _get_job(db: Session, job_id: str | UUID) -> Optional[ScanJob]:
    """Fetch a ScanJob by id without leaking session management."""
    normalized = _normalize_job_id(job_id)
    if normalized is None:
        return None
    return db.query(ScanJob).filter(ScanJob.id == normalized).first()


def mark_job_status(job_id: str, status: str, *, completed: bool = False) -> Optional[ScanJob]:
    """Update a job's status (and optionally completion timestamp)."""
    normalized = _normalize_job_id(job_id)
    if normalized is None:
        logger.warning("Job %s has invalid UUID format", job_id)
        return None

    db = SessionLocal()
    try:
        job = _get_job(db, normalized)
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
    normalized = _normalize_job_id(job_id)
    if normalized is None:
        logger.warning("Dropping engine result for invalid job id %s (%s)", job_id, engine)
        return False

    db = SessionLocal()
    try:
        payload = result or {}
        payload.setdefault("engine", engine)
        payload.setdefault("status", status)

        job = _get_job(db, normalized)
        if not job:
            logger.warning("Dropping engine result for missing job %s (%s)", job_id, engine)
            return False

        scanned_at = datetime.now(timezone.utc)
        stmt = insert(EngineResult).values(
            job_id=normalized,
            engine=engine,
            status=status,
            result=payload,
            scanned_at=scanned_at,
        )

        if db.bind and db.bind.dialect.name == "postgresql":
            stmt = stmt.on_conflict_do_update(
                constraint="uq_engine_results_job_engine",
                set_={
                    "status": status,
                    "result": payload,
                    "scanned_at": scanned_at,
                },
            )
        else:
            stmt = stmt.on_conflict_do_update(
                index_elements=[EngineResult.job_id, EngineResult.engine],
                set_={
                    "status": status,
                    "result": payload,
                    "scanned_at": scanned_at,
                },
            )
        db.execute(stmt)
        db.commit()
        return True
    except SQLAlchemyError:
        logger.exception("Error persisting engine result for job %s engine %s", job_id, engine)
        db.rollback()
        return False
    finally:
        db.close()


def record_dispatch_error(job_id: str, message: str) -> None:
    """Persist an orchestrator-level error for observability and debugging."""
    logger.error("Dispatcher error for job %s: %s", job_id, message)
    record_engine_result(job_id, "Orchestrator", "error", {"error": message})
    mark_job_status(job_id, "error", completed=True)


def _upsert_api_key_usage(
    db: Session,
    api_key_id: UUID,
    job_id: UUID,
    status: str,
    verdict: str | None,
) -> None:
    stmt = insert(ApiKeyUsage).values(
        api_key_id=api_key_id,
        job_id=job_id,
        status=status,
        verdict=verdict,
        created_at=datetime.now(timezone.utc),
    )

    if db.bind and db.bind.dialect.name == "postgresql":
        stmt = stmt.on_conflict_do_update(
            constraint="uq_api_key_usages_key_job",
            set_={"status": status, "verdict": verdict},
        )
    else:
        stmt = stmt.on_conflict_do_update(
            index_elements=[ApiKeyUsage.api_key_id, ApiKeyUsage.job_id],
            set_={"status": status, "verdict": verdict},
        )
    db.execute(stmt)


def finalize_job_summary(job_id: str) -> Optional[dict]:
    """Mark job completion and return an aggregated summary."""
    normalized = _normalize_job_id(job_id)
    if normalized is None:
        logger.warning("Attempted to finalize invalid job id %s", job_id)
        return None

    db = SessionLocal()
    try:
        job = _get_job(db, normalized)
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
        summary = summarize_job(job, engine_results)

        if job.api_key_id:
            _upsert_api_key_usage(
                db,
                job.api_key_id,
                job.id,
                job.status,
                summary.get("verdict"),
            )

        db.commit()
        db.refresh(job)

        return summary
    finally:
        db.close()


def load_engine_registry() -> Dict:
    """Expose active engine registry for callers that cannot import registry directly."""
    return get_active_engines()


def run_all_engines(job_id: str, file_path: str):
    """Compatibility shim: enqueue the Celery-based orchestration."""
    normalized = _normalize_job_id(job_id)
    if normalized is None:
        logger.warning("Refusing to enqueue job with invalid UUID: %s", job_id)
        return None

    try:
        # Local import to avoid circular dependency during module load
        from app.workers.tasks import run_scan
    except Exception as exc:  # noqa: BLE001 - best-effort compatibility
        logger.error("Unable to enqueue job %s: %s", job_id, exc)
        return None

    return run_scan.delay(str(normalized), file_path)
