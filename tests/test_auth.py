import hashlib
import secrets

import pytest
import httpx

from app.db.models import APIKey
from app.db.session import SessionLocal


def _create_test_key(*, name: str = "test", rate_limit_per_day: int = 60) -> str:
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    db = SessionLocal()
    try:
        db.add(
            APIKey(
                key_hash=key_hash,
                name=name,
                rate_limit_per_day=rate_limit_per_day,
            )
        )
        db.commit()
    finally:
        db.close()

    return raw_key


def test_missing_api_key_returns_401(client: httpx.Client):
    response = client.post("/api/v1/scan/", files={"file": ("test.bin", b"data")})
    assert response.status_code == 401


def test_valid_api_key_allows_access(client: httpx.Client):
    raw_key = _create_test_key(rate_limit_per_day=10)
    response = client.post(
        "/api/v1/scan/",
        files={"file": ("test.bin", b"data")},
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 200


def test_rate_limit_enforcement(client: httpx.Client):
    raw_key = _create_test_key(rate_limit_per_day=10)

    last = None
    for i in range(11):  # exceed 10/day
        payload = f"data-{i}".encode("utf-8")
        last = client.post(
            "/api/v1/scan/",
            files={"file": (f"file{i}.bin", payload)},
            headers={"X-API-Key": raw_key},
        )

    assert last is not None
    assert last.status_code == 429
