from concurrent.futures import ThreadPoolExecutor

from uuid import UUID

import hashlib

from app.db.models import APIKey, ApiKeyUsage, EngineResult, File, ScanJob
from app.db.session import SessionLocal
from app.services.orchestrator.dispatcher import finalize_job_summary, record_engine_result


def _create_job() -> str:
    with SessionLocal() as session:
        job = ScanJob(status="running...")
        session.add(job)
        session.commit()
        session.refresh(job)
        return str(job.id)


def _get_engine_result(job_id: str) -> EngineResult:
    job_uuid = UUID(job_id)
    with SessionLocal() as session:
        result = (
            session.query(EngineResult)
            .filter(EngineResult.job_id == job_uuid)
            .one()
        )
        session.expunge(result)
        return result


def _count_results(job_id: str, engine: str) -> int:
    job_uuid = UUID(job_id)
    with SessionLocal() as session:
        return (
            session.query(EngineResult)
            .filter(EngineResult.job_id == job_uuid, EngineResult.engine == engine)
            .count()
        )


def test_record_engine_result_upserts_and_updates_payload():
    job_id = _create_job()
    engine = "clamav"

    assert record_engine_result(job_id, engine, "queued", {"detail": "first"})
    first_result = _get_engine_result(job_id)

    assert first_result.status == "queued"
    assert first_result.result["detail"] == "first"
    assert first_result.result["engine"] == engine
    assert first_result.result["status"] == "queued"
    first_scanned_at = first_result.scanned_at

    assert record_engine_result(job_id, engine, "success", {"detail": "second"})
    updated_result = _get_engine_result(job_id)

    assert updated_result.status == "success"
    assert updated_result.result["detail"] == "second"
    assert updated_result.result["engine"] == engine
    assert updated_result.result["status"] == "success"
    assert updated_result.scanned_at >= first_scanned_at
    assert _count_results(job_id, engine) == 1


def test_record_engine_result_is_idempotent_under_concurrency():
    job_id = _create_job()
    engine = "clamav"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda args: record_engine_result(job_id, engine, args[0], args[1]),
                [
                    ("error", {"attempt": 1}),
                    ("success", {"attempt": 2}),
                ],
            )
        )

    assert all(results)
    final_result = _get_engine_result(job_id)
    assert final_result.status in {"success", "error"}
    assert final_result.result["engine"] == engine
    assert final_result.result["status"] in {"success", "error"}
    assert final_result.result["attempt"] in {1, 2}
    assert _count_results(job_id, engine) == 1


def test_finalize_job_summary_updates_api_key_usage():
    with SessionLocal() as session:
        api_key = APIKey(
            key_hash=hashlib.sha256(b"client-key").hexdigest(),
            name="client",
            rate_limit_per_day=100,
        )
        file_record = File(sha256="deadbeef", path="/tmp/file", filename="sample.bin")
        job = ScanJob(file=file_record, api_key=api_key, status="running...")
        result = EngineResult(
            job=job,
            engine="stub",
            status="success",
            result={"engine": "stub", "status": "ok", "verdict": "clean"},
        )
        session.add_all([api_key, file_record, job, result])
        session.commit()
        job_id = str(job.id)

    summary = finalize_job_summary(job_id)
    assert summary is not None
    assert summary["verdict"] == "clean"

    with SessionLocal() as session:
        usage = (
            session.query(ApiKeyUsage)
            .filter(ApiKeyUsage.job_id == job.id)
            .one()
        )
        refreshed_job = session.query(ScanJob).filter(ScanJob.id == job.id).one()

    assert usage.status == refreshed_job.status
    assert usage.verdict == "clean"
    assert refreshed_job.completed_at is not None
