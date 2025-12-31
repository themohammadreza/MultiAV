import hashlib
from uuid import uuid4

import httpx

from app.core.security import hash_password
from app.db.models import AdminUser, APIKey, ApiKeyAuditLog
from app.db.session import SessionLocal


def _login_admin(client: httpx.Client, username: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/admin/auth/login/",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _create_admin(username: str, password: str, is_superadmin: bool = False) -> AdminUser:
    with SessionLocal() as db:
        user = AdminUser(
            username=username,
            password_hash=hash_password(password),
            is_superadmin=is_superadmin,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def test_superadmin_can_manage_admin_users(client: httpx.Client):
    headers = _login_admin(client, "admin", "admin")

    response = client.post(
        "/api/v1/admin/users/",
        headers=headers,
        json={"username": "operator", "password": "password", "is_superadmin": False},
    )
    assert response.status_code == 200
    user_id = response.json()["id"]

    response = client.patch(
        f"/api/v1/admin/users/{user_id}/",
        headers=headers,
        json={"is_superadmin": True, "is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["is_superadmin"] is True
    assert response.json()["is_active"] is False

    response = client.delete(
        f"/api/v1/admin/users/{user_id}/",
        headers=headers,
    )
    assert response.status_code == 200


def test_superadmin_cannot_deactivate_last_active_superadmin(client: httpx.Client):
    headers = _login_admin(client, "admin", "admin")

    response = client.get("/api/v1/admin/users/", headers=headers)
    assert response.status_code == 200
    superadmin = response.json()[0]

    response = client.patch(
        f"/api/v1/admin/users/{superadmin['id']}/",
        headers=headers,
        json={"is_active": False},
    )
    assert response.status_code == 400


def test_superadmin_cannot_deactivate_self(client: httpx.Client):
    headers = _login_admin(client, "admin", "admin")
    me_response = client.get("/api/v1/admin/users/me/", headers=headers)
    assert me_response.status_code == 200
    my_id = me_response.json()["id"]

    response = client.patch(
        f"/api/v1/admin/users/{my_id}/",
        headers=headers,
        json={"is_active": False},
    )
    assert response.status_code == 400


def test_superadmin_must_confirm_current_password_for_self_update(client: httpx.Client):
    headers = _login_admin(client, "admin", "admin")
    me_response = client.get("/api/v1/admin/users/me/", headers=headers)
    assert me_response.status_code == 200
    my_id = me_response.json()["id"]

    missing_response = client.patch(
        f"/api/v1/admin/users/{my_id}/",
        headers=headers,
        json={"password": "new-secret"},
    )
    assert missing_response.status_code == 400

    wrong_response = client.patch(
        f"/api/v1/admin/users/{my_id}/",
        headers=headers,
        json={"password": "new-secret", "current_password": "wrong"},
    )
    assert wrong_response.status_code == 400

    ok_response = client.patch(
        f"/api/v1/admin/users/{my_id}/",
        headers=headers,
        json={"password": "new-secret", "current_password": "admin"},
    )
    assert ok_response.status_code == 200


def test_superadmin_cannot_delete_self(client: httpx.Client):
    headers = _login_admin(client, "admin", "admin")
    me_response = client.get("/api/v1/admin/users/me/", headers=headers)
    assert me_response.status_code == 200
    my_id = me_response.json()["id"]

    response = client.delete(
        f"/api/v1/admin/users/{my_id}/",
        headers=headers,
    )
    assert response.status_code == 400


def test_delete_admin_with_audit_logs_returns_clear_error(client: httpx.Client):
    headers = _login_admin(client, "admin", "admin")
    admin_user = _create_admin("audited", "audited-password", is_superadmin=True)

    with SessionLocal() as db:
        api_key = APIKey(
            key_hash=hashlib.sha256(b"audit-key").hexdigest(),
            name="audit-key",
            rate_limit_per_day=10,
        )
        db.add(api_key)
        db.flush()
        log = ApiKeyAuditLog(
            api_key_id=api_key.id,
            action="create",
            performed_by_admin_id=admin_user.id,
            performed_by_username=admin_user.username,
            metadata_json={"note": "audit"},
        )
        db.add(log)
        db.commit()

    response = client.delete(
        f"/api/v1/admin/users/{admin_user.id}/",
        headers=headers,
    )
    assert response.status_code == 400


def test_non_superadmin_permissions_are_limited(client: httpx.Client):
    regular_admin = _create_admin("viewer", "viewer-password", is_superadmin=False)
    headers = _login_admin(client, "viewer", "viewer-password")

    response = client.get("/api/v1/admin/users/", headers=headers)
    assert response.status_code == 403

    response = client.get("/api/v1/admin/users/me/", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == str(regular_admin.id)

    response = client.patch(
        f"/api/v1/admin/users/{regular_admin.id}/",
        headers=headers,
        json={"username": "new-name", "password": "new-pass"},
    )
    assert response.status_code == 403
