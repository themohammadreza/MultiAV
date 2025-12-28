import httpx

from app.core.security import hash_password
from app.db.models import AdminUser
from app.db.session import SessionLocal


def test_admin_login_and_me_with_cookie(client: httpx.Client):
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["token"]

    me_response = client.get("/api/v1/admin/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "admin"
    assert me_response.json()["is_superadmin"] is True


def test_admin_auth_required(client: httpx.Client):
    response = client.get("/api/v1/admin/keys/")
    assert response.status_code == 401


def test_admin_me_reflects_non_superadmin_role(client: httpx.Client):
    with SessionLocal() as db:
        admin = AdminUser(
            username="viewer",
            password_hash=hash_password("viewer-password"),
            is_superadmin=False,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

    login_response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "viewer", "password": "viewer-password"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["token"]

    me_response = client.get(
        "/api/v1/admin/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    payload = me_response.json()
    assert payload["username"] == "viewer"
    assert payload["is_superadmin"] is False
