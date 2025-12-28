import hashlib
import secrets
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from app.db.models import APIKey, ApiKeyUsage, File, ScanJob
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


def test_list_create_keys_without_trailing_slash(client: httpx.Client):
    admin_key = _create_admin_key()

    create_response = client.post(
        "/api/v1/admin/keys",
        json={"name": "service-no-slash", "rate_limit_per_day": 25},
        headers={"X-API-Key": admin_key},
    )
    assert create_response.status_code == 200
    key_id = create_response.json()["id"]

    list_response = client.get(
        "/api/v1/admin/keys",
        headers={"X-API-Key": admin_key},
    )
    assert list_response.status_code == 200
    keys = list_response.json()
    assert any(item["id"] == key_id for item in keys)


def test_list_key_scans(client: httpx.Client):
    admin_key = _create_admin_key("admin")
    db = SessionLocal()
    try:
        api_key = APIKey(key_hash=hashlib.sha256(b"client-key").hexdigest(), name="client", rate_limit_per_day=10)
        db.add(api_key)
        db.flush()
        api_key_id = api_key.id
        file_entry = File(id=uuid4(), sha256="a" * 64, path="/tmp/file", filename="sample.bin")
        db.add(file_entry)
        job = ScanJob(id=uuid4(), file_id=file_entry.id, api_key_id=api_key.id, status="done")
        db.add(job)
        job_id = job.id
        usage = ApiKeyUsage(
            api_key_id=api_key.id,
            job_id=job.id,
            status="done",
            verdict="clean",
            created_at=datetime.now(timezone.utc),
        )
        db.add(usage)
        db.commit()
    finally:
        db.close()

    response = client.get(
        f"/api/v1/admin/keys/{api_key_id}/scans",
        headers={"X-API-Key": admin_key},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["count"] == 1
    assert payload["items"][0]["job_id"] == str(job_id)


def test_admin_key_invalid_uuid_returns_404(client: httpx.Client):
    admin_key = _create_admin_key()

    update_response = client.patch(
        "/api/v1/admin/keys/not-a-uuid",
        json={"name": "nope"},
        headers={"X-API-Key": admin_key},
    )
    assert update_response.status_code == 404

    revoke_response = client.post(
        "/api/v1/admin/keys/not-a-uuid/revoke",
        headers={"X-API-Key": admin_key},
    )
    assert revoke_response.status_code == 404

    scans_response = client.get(
        "/api/v1/admin/keys/not-a-uuid/scans",
        headers={"X-API-Key": admin_key},
    )
    assert scans_response.status_code == 404


def test_revoked_key_rejected_for_ui_requests(client: httpx.Client):
    admin_key = _create_admin_key()

    create_response = client.post(
        "/api/v1/admin/keys/",
        json={"name": "client", "rate_limit_per_day": 10},
        headers={"X-API-Key": admin_key},
    )
    assert create_response.status_code == 200
    payload = create_response.json()
    key_id = payload["id"]
    raw_key = payload["raw_key"]

    revoke_response = client.post(
        f"/api/v1/admin/keys/{key_id}/revoke",
        headers={"X-API-Key": admin_key},
    )
    assert revoke_response.status_code == 200

    response = client.get(
        "/api/v1/ui/jobs/recent",
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 401
