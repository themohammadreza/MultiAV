from datetime import datetime
from typing import Callable

from app.db.models import EngineResult, ScanJob
from app.db.session import SessionLocal
from app.services.orchestrator.registry import get_active_engines

EngineRunner = Callable[[str], dict]


def _record_dispatch_error(db, job_id: str, message: str) -> None:
    """Persist a dispatcher-level error to aid troubleshooting."""
    db.add(
        EngineResult(
            job_id=job_id,
            engine="Orchestrator",
            status="error",
            result={"error": message},
        )
    )
    db.commit()


def run_all_engines(job_id: str, file_path: str) -> None:
    """Execute all configured engines for a job and persist their results.

    Args:
        job_id: UUID of the ScanJob as a string.
        file_path: Absolute path to the file to scan.
    """
    db = SessionLocal()
    try:
        job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
        if not job:
            return

        job.status = "running..."
        db.commit()

        try:
            engine_registry = get_active_engines()
            if not engine_registry:
                _record_dispatch_error(db, job_id, "No engines configured or enabled")
                job.status = "error"
                job.completed_at = datetime.utcnow()
                db.commit()
                return

            for name, definition in engine_registry.items():
                _run_engine(db, definition["runner"], name, job_id, file_path)

            job.status = "done"
            job.completed_at = datetime.utcnow()
            db.commit()
        except Exception as exc:  # noqa: BLE001 - log and persist failure instead of dropping job
            _record_dispatch_error(db, job_id, f"Dispatcher failure: {exc}")
            job.status = "error"
            job.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def _run_engine(
    db,
    runner: EngineRunner,
    name: str,
    job_id: str,
    file_path: str,
) -> None:
    """Run a single engine, capturing success or error.

    Args:
        db: Active SQLAlchemy session.
        runner: Callable that scans a file path and returns a result payload.
        name: Engine name used for persistence and reporting.
        job_id: UUID of the ScanJob as a string.
        file_path: Absolute path to the file to scan.
    """
    try:
        result_payload = runner(file_path)
        entry = EngineResult(
            job_id=job_id,
            engine=name,
            status="success",
            result=result_payload,
        )
    except Exception as exc:
        entry = EngineResult(
            job_id=job_id,
            engine=name,
            status="error",
            result={"error": str(exc)},
        )

    db.add(entry)
    db.commit()
