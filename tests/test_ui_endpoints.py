import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from app.db.models import EngineResult, File, ScanJob
from app.db.session import SessionLocal
from app.main import app
from app.services.orchestrator.registry import AVAILABLE_ENGINES
from tests.utils import configure_stub_engines


client = TestClient(app)


def seed_job(status: str = "done") -> str:
    db = SessionLocal()
    file = File(sha256="abc123", path="/tmp/file")
    job = ScanJob(file=file, status=status)
    result = EngineResult(
        job=job,
        engine="stub",
        status="success",
        result={"engine": "stub", "status": "ok", "verdict": "clean"},
    )
    db.add_all([file, job, result])
    db.commit()
    job_id = str(job.id)
    db.close()
    return job_id


def test_recent_jobs_returns_summary():
    job_id = seed_job()
    response = client.get("/api/v1/ui/jobs/recent")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["job_id"] == job_id
    assert payload["items"][0]["verdict"] == "clean"
    assert payload["items"][0]["sha256"] == "abc123"


def test_recent_jobs_filters_by_severity_and_job():
    job_id = seed_job(status="done")
    # inject a severity to test filter pass
    with SessionLocal() as session:
        job = session.query(ScanJob).filter(ScanJob.id == job_id).first()
        if job and job.results:
            job.results[0].result["severity"] = "high"
            session.commit()

    # Partial job id filter should work without UUID casting errors
    response = client.get(f"/api/v1/ui/jobs/recent?severity=high&job_id={job_id[:4]}")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["job_id"] == job_id


def test_active_engines_uses_registry(monkeypatch):
    configure_stub_engines(
        monkeypatch,
        {"stub": {"runner": AVAILABLE_ENGINES["clamav"], "timeout": 7, "weight": 2.0}},
    )

    response = client.get("/api/v1/ui/engines/active")
    assert response.status_code == 200
    engines = response.json()["engines"]
    assert any(e["engine"] == "stub" and e["timeout"] == 7 and e["weight"] == 2.0 for e in engines)
