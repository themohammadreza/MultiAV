import hashlib
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

from app.db.models import EngineResult, File, ScanJob
from app.db.session import SessionLocal
from app.services.aggregator import summary
from app.services.orchestrator import registry
from app.services.storage import get_storage_service
from app.workers import tasks


DEFAULT_ENGINE_WEIGHT = 0.5


def configure_stub_engines(monkeypatch, engine_map: Dict[str, dict]):
    monkeypatch.setattr(registry, "get_active_engines", lambda config_path=None: engine_map)
    monkeypatch.setattr(
        summary,
        "get_active_engines",
        lambda config_path=None: engine_map,
    )
    monkeypatch.setattr(
        summary,
        "get_engine_weights",
        lambda engine_registry=None, config_path=None: {
            name: meta.get("weight", DEFAULT_ENGINE_WEIGHT) for name, meta in engine_map.items()
        },
    )
    monkeypatch.setattr(tasks, "get_active_engines", lambda: engine_map)


def stage_file_and_job(content: bytes) -> tuple[ScanJob, str]:
    storage = get_storage_service()
    digest = hashlib.sha256(content).hexdigest()
    dir_path = Path(storage.base_path) / digest
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / "original"
    file_path.write_bytes(content)

    with SessionLocal() as session:
        file_rec = session.query(File).filter(File.sha256 == digest).first()
        if not file_rec:
            file_rec = File(sha256=digest, path=str(file_path))
            session.add(file_rec)
            session.commit()
            session.refresh(file_rec)

        job = ScanJob(file_id=file_rec.id)
        session.add(job)
        session.commit()
        session.refresh(job)
        session.expunge(job)
        return job, str(file_path)


def cache_lookup(content: bytes) -> Optional[ScanJob]:
    digest = hashlib.sha256(content).hexdigest()
    with SessionLocal() as session:
        file_rec = session.query(File).filter(File.sha256 == digest).first()
        if not file_rec:
            return None
        job = (
            session.query(ScanJob)
            .filter(ScanJob.file_id == file_rec.id)
            .order_by(ScanJob.created_at.desc())
            .first()
        )
        if job:
            session.expunge(job)
        return job


def wait_for_job_status(job_id: str, *, timeout: float = 30.0, terminal_statuses=None) -> ScanJob:
    terminal_statuses = terminal_statuses or {"done", "done_with_errors", "error"}
    deadline = time.time() + timeout

    while time.time() < deadline:
        with SessionLocal() as session:
            job = (
                session.query(ScanJob)
                .filter(ScanJob.id == uuid.UUID(str(job_id)))
                .first()
            )
            if job and job.status in terminal_statuses and job.completed_at is not None:
                session.expunge(job)
                return job
        time.sleep(0.1)

    raise AssertionError(f"Job {job_id} did not reach terminal status within {timeout}s")


def load_engine_results(job_id) -> list[EngineResult]:
    with SessionLocal() as session:
        results = (
            session.query(EngineResult)
            .filter(EngineResult.job_id == uuid.UUID(str(job_id)))
            .all()
        )
        for result in results:
            session.expunge(result)
        return results


def summarize_job(job_id: str) -> dict:
    with SessionLocal() as session:
        job = session.query(ScanJob).filter(ScanJob.id == uuid.UUID(str(job_id))).first()
        if not job:
            raise RuntimeError("job missing")
        engine_results = sorted(job.results, key=lambda r: r.scanned_at or job.created_at)
        return summary.summarize_job(job, engine_results)


def execute_scan(job_id: str, file_path: str) -> None:
    result = tasks.run_scan.apply(args=[job_id, file_path])
    result.get(timeout=30)
