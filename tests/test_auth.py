import hashlib
import secrets

import pytest
from fastapi.testclient import TestClient

from app.db.models import APIKey
from app.db.session import SessionLocal
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _create_test_key(*, name: str = "test", rate_limit_per_minute: int = 60) -> str:
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    db = SessionLocal()
    try:
        db.add(
            APIKey(
                key_hash=key_hash,
                name=name,
                rate_limit_per_minute=rate_limit_per_minute,
            )
        )
        db.commit()
    finally:
        db.close()

    return raw_key


def test_missing_api_key_returns_401(client: TestClient):
    response = client.post("/api/v1/scan/", files={"file": ("test.bin", b"data")})
    assert response.status_code == 401


def test_valid_api_key_allows_access(client: TestClient):
    raw_key = _create_test_key(rate_limit_per_minute=10)
    response = client.post(
        "/api/v1/scan/",
        files={"file": ("test.bin", b"data")},
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 200


def test_rate_limit_enforcement(client: TestClient):
    raw_key = _create_test_key(rate_limit_per_minute=10)

    last = None
    for i in range(11):  # exceed 10/min
        last = client.post(
            "/api/v1/scan/",
            files={"file": (f"file{i}.bin", b"data")},
            headers={"X-API-Key": raw_key},
        )

    assert last is not None
    assert last.status_code == 429
