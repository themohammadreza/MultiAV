import hashlib
import secrets
import time

import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from app.db.models import APIKey
from app.db.session import SessionLocal
from app.main import app
from tests.utils import configure_stub_engines


@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def api_key_header():
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    db = SessionLocal()
    try:
        db.add(APIKey(key_hash=key_hash, name="test-suite", rate_limit_per_minute=10_000))
        db.commit()
    finally:
        db.close()

    return {"X-API-Key": raw_key}


@pytest.mark.integration
def test_upload_scan_retrieve_flow(monkeypatch, client, api_key_header, celery_worker_instance):
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
    assert "api-test" in result["details"]


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
