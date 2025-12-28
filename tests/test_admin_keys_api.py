import hashlib
import secrets

import httpx

from app.db.models import APIKey
from app.db.session import SessionLocal


def _create_admin_key(name: str = "admin") -> str:
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    db = SessionLocal()
    try:
        db.add(APIKey(key_hash=key_hash, name=name, rate_limit_per_day=100))
        db.commit()
    finally:
        db.close()
    return raw_key


def test_create_list_rotate_revoke_keys(client: httpx.Client):
    admin_key = _create_admin_key()

    create_response = client.post(
        "/api/v1/admin/keys/",
        json={"name": "service-a", "rate_limit_per_day": 50},
        headers={"X-API-Key": admin_key},
    )
    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["raw_key"]
    key_id = create_payload["id"]

    list_response = client.get(
        "/api/v1/admin/keys/",
        headers={"X-API-Key": admin_key},
    )
    assert list_response.status_code == 200
    keys = list_response.json()
    assert any(item["id"] == key_id for item in keys)

    rotate_response = client.patch(
        f"/api/v1/admin/keys/{key_id}",
        json={"rotate": True, "name": "service-a-rotated"},
        headers={"X-API-Key": admin_key},
    )
    assert rotate_response.status_code == 200
    rotate_payload = rotate_response.json()
    assert rotate_payload["raw_key"]
    assert rotate_payload["name"] == "service-a-rotated"

    revoke_response = client.post(
        f"/api/v1/admin/keys/{key_id}/revoke",
        headers={"X-API-Key": admin_key},
    )
    assert revoke_response.status_code == 200
    revoke_payload = revoke_response.json()
    assert revoke_payload["revoked_at"] is not None
