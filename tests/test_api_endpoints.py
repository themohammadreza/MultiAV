import hashlib
import secrets
import time
from datetime import datetime, timezone
import uuid

import pytest
import httpx

from app.db.models import APIKey, ApiKeyUsage, File as FileModel, ScanJob
from app.db.session import SessionLocal
from tests.utils import configure_stub_engines


@pytest.fixture
def api_key_header():
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    db = SessionLocal()
    try:
        # Keep this intentionally small to ensure cached scans don't consume quota.
        db.add(APIKey(key_hash=key_hash, name="test-suite", rate_limit_per_day=1))
        db.commit()
    finally:
        db.close()

    return {"X-API-Key": raw_key}


@pytest.mark.integration
def test_upload_scan_retrieve_flow(monkeypatch, client: httpx.Client, api_key_header, celery_worker_instance):
    def ok_runner(path: str):  # noqa: ARG001
        return {"engine": "api-test", "status": "ok", "detected": False, "verdict": "clean"}

    configure_stub_engines(
        monkeypatch,
        {"api-test": {"runner": ok_runner, "timeout": 5, "weight": 1.0}},
    )

    response = client.post(
        "/api/v1/scan/",
        files={"file": ("test.txt", b"hello api", "text/plain")},
        headers=api_key_header,
    )

    assert response.status_code == 200
    data = response.json()
    job_id = data["job_id"]

    result = None
    for _ in range(60):
        result_response = client.get(f"/api/v1/results/{job_id}", headers=api_key_header)
        assert result_response.status_code == 200
        result = result_response.json()
        if result["status"] in {"done", "done_with_errors", "error"}:
            break
        time.sleep(0.25)

    assert result is not None
    assert result["status"] == "done"
    assert result["verdict"] == "clean"
    assert result["filename"] == "test.txt"
    assert "api-test" in result["details"]

    key_hash = hashlib.sha256(api_key_header["X-API-Key"].encode("utf-8")).hexdigest()
    with SessionLocal() as session:
        api_key = session.query(APIKey).filter(APIKey.key_hash == key_hash).first()
        usage = (
            session.query(ApiKeyUsage)
            .filter(ApiKeyUsage.job_id == uuid.UUID(job_id))
            .one()
        )

    assert api_key is not None
    assert usage.api_key_id == api_key.id
    assert usage.status == "done"
    assert usage.verdict == "clean"
    assert usage.created_at is not None


@pytest.mark.integration
def test_upload_returns_cached_for_duplicate(monkeypatch, client, api_key_header, celery_worker_instance):
    configure_stub_engines(
        monkeypatch,
        {"api-cache": {"runner": lambda p: {"engine": "api-cache", "status": "ok"}, "timeout": 5}},
    )

    content = b"duplicate content"
    r1 = client.post(
        "/api/v1/scan/",
        files={"file": ("f1.bin", content, "application/octet-stream")},
        headers=api_key_header,
    )
    job1 = r1.json()

    r2 = client.post(
        "/api/v1/scan/",
        files={"file": ("f2.bin", content, "application/octet-stream")},
        headers=api_key_header,
    )
    job2 = r2.json()

    assert job2["cached"] is True
    assert job2["job_id"] == job1["job_id"]


def test_duplicate_with_different_api_key_creates_new_job(monkeypatch, client, celery_worker_instance):
    configure_stub_engines(
        monkeypatch,
        {"api-cache": {"runner": lambda p: {"engine": "api-cache", "status": "ok"}, "timeout": 5}},
    )

    # key one
    raw_key1 = secrets.token_urlsafe(16)
    key_hash1 = hashlib.sha256(raw_key1.encode("utf-8")).hexdigest()
    raw_key2 = secrets.token_urlsafe(16)
    key_hash2 = hashlib.sha256(raw_key2.encode("utf-8")).hexdigest()

    db = SessionLocal()
    try:
        db.add_all(
            [
                APIKey(key_hash=key_hash1, name="key-one", rate_limit_per_day=10),
                APIKey(key_hash=key_hash2, name="key-two", rate_limit_per_day=10),
            ]
        )
        db.commit()
    finally:
        db.close()

    content = b"duplicate content two keys"
    r1 = client.post(
        "/api/v1/scan/",
        files={"file": ("f1.bin", content, "application/octet-stream")},
        headers={"X-API-Key": raw_key1},
    )
    job1 = r1.json()

    r2 = client.post(
        "/api/v1/scan/",
        files={"file": ("f2.bin", content, "application/octet-stream")},
        headers={"X-API-Key": raw_key2},
    )
    job2 = r2.json()

    assert job2["cached"] is False
    assert job2["job_id"] != job1["job_id"]


@pytest.mark.integration
@pytest.mark.parametrize("status", ["error", "done_with_errors"])
def test_duplicate_does_not_cache_terminal_errors(
    status, client, api_key_header, celery_worker_instance
):
    content = b"error cache content"
    digest = hashlib.sha256(content).hexdigest()
    key_hash = hashlib.sha256(api_key_header["X-API-Key"].encode("utf-8")).hexdigest()

    db = SessionLocal()
    try:
        api_key = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()
        file_rec = FileModel(sha256=digest, path=f"/tmp/{digest}")
        db.add(file_rec)
        db.commit()
        db.refresh(file_rec)

        job = ScanJob(
            file_id=file_rec.id,
            api_key_id=api_key.id if api_key else None,
            status=status,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
    finally:
        db.close()

    response = client.post(
        "/api/v1/scan/",
        files={"file": ("error.bin", content, "application/octet-stream")},
        headers=api_key_header,
    )

    data = response.json()
    assert data["cached"] is False
    assert data["job_id"] != str(job.id)


@pytest.mark.integration
def test_get_results_401_without_api_key(client):
    response = client.get("/api/v1/results/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 401


@pytest.mark.integration
def test_get_results_404_for_unknown_job(client, api_key_header):
    response = client.get(
        "/api/v1/results/00000000-0000-0000-0000-000000000001",
        headers=api_key_header,
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
