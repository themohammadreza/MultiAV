import hashlib
import httpx
import pytest
import secrets
import uuid

from app.db.models import APIKey, EngineResult, File, ScanJob
from app.db.session import SessionLocal
from app.services.orchestrator.registry import AVAILABLE_ENGINES
from tests.utils import configure_stub_engines


def _create_api_key(name: str = "ui-test") -> tuple[str, APIKey]:
    raw_key = secrets.token_urlsafe(16)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    db = SessionLocal()
    api_key = APIKey(key_hash=key_hash, name=name, rate_limit_per_day=100)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    db.close()
    return raw_key, api_key


def seed_job(status: str = "done", api_key_id=None, sha256: str = "abc123", filename: str = "sample.bin") -> str:
    db = SessionLocal()
    file = File(sha256=sha256, path="/tmp/file", filename=filename)
    job = ScanJob(file=file, status=status, api_key_id=api_key_id)
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


def test_recent_jobs_returns_summary(client: httpx.Client):
    raw_key, api_key = _create_api_key()
    job_id = seed_job(api_key_id=api_key.id)
    response = client.get("/api/v1/ui/jobs/recent/", headers={"X-API-Key": raw_key})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["job_id"] == job_id
    assert payload["items"][0]["verdict"] == "clean"
    assert payload["items"][0]["sha256"] == "abc123"
    assert payload["items"][0]["filename"] == "sample.bin"


def test_recent_jobs_filters_by_severity_and_job(client: httpx.Client):
    raw_key, api_key = _create_api_key()
    job_id = seed_job(status="done", api_key_id=api_key.id)
    # inject a severity to test filter pass
    with SessionLocal() as session:
        job = session.query(ScanJob).filter(ScanJob.id == uuid.UUID(job_id)).first()
        if job and job.results:
            job.results[0].result["severity"] = "high"
            session.commit()

    # Partial job id filter should work without UUID casting errors
    response = client.get(
        f"/api/v1/ui/jobs/recent/?severity=high&job_id={job_id[:4]}",
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["job_id"] == job_id


def test_recent_jobs_requires_api_key(client: httpx.Client):
    response = client.get("/api/v1/ui/jobs/recent/")
    assert response.status_code == 401


def test_recent_jobs_scoped_to_api_key(client: httpx.Client):
    raw_key_1, api_key_1 = _create_api_key(name="key-one")
    raw_key_2, api_key_2 = _create_api_key(name="key-two")

    job_one = seed_job(api_key_id=api_key_1.id, sha256="abc123")
    seed_job(api_key_id=api_key_2.id, sha256="def456")

    response = client.get("/api/v1/ui/jobs/recent/", headers={"X-API-Key": raw_key_1})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["job_id"] == job_one


def test_active_engines_uses_registry(monkeypatch, client: httpx.Client):
    configure_stub_engines(
        monkeypatch,
        {"stub": {"runner": AVAILABLE_ENGINES["clamav"], "timeout": 7, "weight": 2.0}},
    )

    response = client.get("/api/v1/ui/engines/active/")
    assert response.status_code == 200
    engines = response.json()["engines"]
    assert any(e["engine"] == "stub" and e["timeout"] == 7 and e["weight"] == 2.0 for e in engines)


def test_health_endpoint(client: httpx.Client):
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "ok"
    assert payload.get("checks") == {"database": "ok", "storage": "ok"}


def test_health_endpoint_db_failure(monkeypatch, client: httpx.Client):
    from app.api.v1 import health as health_module

    monkeypatch.setattr(health_module, "_check_database", lambda: (False, "db down"))

    response = client.get("/api/v1/health/")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["checks"]["database"] == "error"
    assert payload["errors"]["database"] == "db down"


def test_health_endpoint_storage_failure(monkeypatch, client: httpx.Client):
    from app.api.v1 import health as health_module

    monkeypatch.setattr(health_module, "_check_storage", lambda: (False, "storage down"))

    response = client.get("/api/v1/health/")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["checks"]["storage"] == "error"
    assert payload["errors"]["storage"] == "storage down"
