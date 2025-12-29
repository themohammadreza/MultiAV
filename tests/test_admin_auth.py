import httpx

from app.core.security import hash_password
from app.db.models import AdminUser
from app.db.session import SessionLocal


def test_admin_login_and_me_with_cookie(client: httpx.Client):
    response = client.post(
        "/api/v1/admin/auth/login/",
        json={"username": "admin", "password": "admin"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["token"]

    me_response = client.get("/api/v1/admin/auth/me/")
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
        "/api/v1/admin/auth/login/",
        json={"username": "viewer", "password": "viewer-password"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["token"]

    me_response = client.get(
        "/api/v1/admin/auth/me/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    payload = me_response.json()
    assert payload["username"] == "viewer"
    assert payload["is_superadmin"] is False


def test_inactive_admin_cannot_login(client: httpx.Client):
    with SessionLocal() as db:
        admin = AdminUser(
            username="inactive-user",
            password_hash=hash_password("inactive-password"),
            is_superadmin=False,
            is_active=False,
        )
        db.add(admin)
        db.commit()

    response = client.post(
        "/api/v1/admin/auth/login/",
        json={"username": "inactive-user", "password": "inactive-password"},
    )
    assert response.status_code == 401


def test_admin_session_rejected_when_deactivated(client: httpx.Client):
    with SessionLocal() as db:
        admin = AdminUser(
            username="temp-user",
            password_hash=hash_password("temp-password"),
            is_superadmin=False,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

    login_response = client.post(
        "/api/v1/admin/auth/login/",
        json={"username": "temp-user", "password": "temp-password"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["token"]

    with SessionLocal() as db:
        admin = db.query(AdminUser).filter(AdminUser.username == "temp-user").first()
        assert admin is not None
        admin.is_active = False
        db.add(admin)
        db.commit()

    me_response = client.get(
        "/api/v1/admin/auth/me/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 401
