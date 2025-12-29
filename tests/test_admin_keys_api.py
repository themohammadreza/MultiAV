from datetime import datetime, timezone
import hashlib
from uuid import UUID, uuid4

import httpx

from app.db.models import APIKey, ApiKeyAuditLog, ApiKeyUsage, File, ScanJob
from app.db.session import SessionLocal


def _login_admin(client: httpx.Client) -> dict[str, str]:
    response = client.post(
        "/api/v1/admin/auth/login/",
        json={"username": "admin", "password": "admin"},
    )
    assert response.status_code == 200
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_list_rotate_revoke_keys(client: httpx.Client):
    headers = _login_admin(client)

    create_response = client.post(
        "/api/v1/admin/keys/",
        json={"name": "service-a", "rate_limit_per_day": 50},
        headers=headers,
    )
    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["raw_key"]
    key_id = create_payload["id"]

    list_response = client.get(
        "/api/v1/admin/keys/",
        headers=headers,
    )
    assert list_response.status_code == 200
    keys = list_response.json()
    assert any(item["id"] == key_id for item in keys)

    rotate_response = client.patch(
        f"/api/v1/admin/keys/{key_id}/",
        json={"rotate": True, "name": "service-a-rotated"},
        headers=headers,
    )
    assert rotate_response.status_code == 200
    rotate_payload = rotate_response.json()
    assert rotate_payload["raw_key"]
    assert rotate_payload["name"] == "service-a-rotated"

    revoke_response = client.post(
        f"/api/v1/admin/keys/{key_id}/revoke/",
        headers=headers,
    )
    assert revoke_response.status_code == 200
    revoke_payload = revoke_response.json()
    assert revoke_payload["revoked_at"] is not None


def test_api_key_audit_logs_capture_admin_username(client: httpx.Client):
    headers = _login_admin(client)

    create_response = client.post(
        "/api/v1/admin/keys/",
        json={"name": "audit-service", "rate_limit_per_day": 75},
        headers=headers,
    )
    assert create_response.status_code == 200
    key_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/admin/keys/{key_id}/",
        json={"name": "audit-service-updated", "rate_limit_per_day": 80},
        headers=headers,
    )
    assert update_response.status_code == 200

    rotate_response = client.patch(
        f"/api/v1/admin/keys/{key_id}/",
        json={"rotate": True},
        headers=headers,
    )
    assert rotate_response.status_code == 200

    revoke_response = client.post(
        f"/api/v1/admin/keys/{key_id}/revoke/",
        headers=headers,
    )
    assert revoke_response.status_code == 200

    db = SessionLocal()
    try:
        logs = (
            db.query(ApiKeyAuditLog)
            .filter(ApiKeyAuditLog.api_key_id == UUID(key_id))
            .all()
        )
    finally:
        db.close()

    actions = {log.action for log in logs}
    assert actions == {"create", "update", "rotate", "revoke"}
    assert len(logs) == 4
    assert all(log.performed_by_username == "admin" for log in logs)
    update_log = next(log for log in logs if log.action == "update")
    assert update_log.metadata_json["old_name"] == "audit-service"
    assert update_log.metadata_json["new_name"] == "audit-service-updated"
    assert update_log.metadata_json["old_rate_limit_per_day"] == 75
    assert update_log.metadata_json["new_rate_limit_per_day"] == 80


def test_list_create_keys_with_trailing_slash(client: httpx.Client):
    headers = _login_admin(client)

    create_response = client.post(
        "/api/v1/admin/keys/",
        json={"name": "service-no-slash", "rate_limit_per_day": 25},
        headers=headers,
    )
    assert create_response.status_code == 200
    key_id = create_response.json()["id"]

    list_response = client.get(
        "/api/v1/admin/keys/",
        headers=headers,
    )
    assert list_response.status_code == 200
    keys = list_response.json()
    assert any(item["id"] == key_id for item in keys)


def test_list_key_scans(client: httpx.Client):
    headers = _login_admin(client)
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
        f"/api/v1/admin/keys/{api_key_id}/scans/",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["count"] == 1
    assert payload["items"][0]["job_id"] == str(job_id)


def test_admin_key_invalid_uuid_returns_404(client: httpx.Client):
    headers = _login_admin(client)

    update_response = client.patch(
        "/api/v1/admin/keys/not-a-uuid/",
        json={"name": "nope"},
        headers=headers,
    )
    assert update_response.status_code == 404

    revoke_response = client.post(
        "/api/v1/admin/keys/not-a-uuid/revoke/",
        headers=headers,
    )
    assert revoke_response.status_code == 404

    scans_response = client.get(
        "/api/v1/admin/keys/not-a-uuid/scans/",
        headers=headers,
    )
    assert scans_response.status_code == 404


def test_revoked_key_rejected_for_ui_requests(client: httpx.Client):
    headers = _login_admin(client)

    create_response = client.post(
        "/api/v1/admin/keys/",
        json={"name": "client", "rate_limit_per_day": 10},
        headers=headers,
    )
    assert create_response.status_code == 200
    payload = create_response.json()
    key_id = payload["id"]
    raw_key = payload["raw_key"]

    revoke_response = client.post(
        f"/api/v1/admin/keys/{key_id}/revoke/",
        headers=headers,
    )
    assert revoke_response.status_code == 200

    response = client.get(
        "/api/v1/ui/jobs/recent",
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 401
