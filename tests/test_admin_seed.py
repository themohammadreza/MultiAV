import pytest

from app.core.admin_seed import ensure_default_admin
from app.db.models import AdminUser
from app.db.session import SessionLocal


def _clear_admins() -> None:
    with SessionLocal() as db:
        db.query(AdminUser).delete()
        db.commit()


def test_ensure_default_admin_warns_when_admin_exists(caplog):
    caplog.set_level("WARNING")
    with SessionLocal() as db:
        admin = db.query(AdminUser).first()
        assert admin is not None

        created = ensure_default_admin(db)

    assert created is None
    assert "admin user already exists" in caplog.text.lower()


def test_ensure_default_admin_requires_env_vars(caplog, monkeypatch):
    caplog.set_level("WARNING")
    _clear_admins()
    monkeypatch.delenv("ADMIN_DEFAULT_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_DEFAULT_PASSWORD", raising=False)

    with SessionLocal() as db:
        with pytest.raises(RuntimeError, match="ADMIN_DEFAULT_USERNAME and ADMIN_DEFAULT_PASSWORD"):
            ensure_default_admin(db)

    assert "default admin seed failed" in caplog.text.lower()
    _clear_admins()


def test_ensure_default_admin_creates_user_and_warns(caplog, monkeypatch):
    caplog.set_level("WARNING")
    _clear_admins()
    monkeypatch.setenv("ADMIN_DEFAULT_USERNAME", "seed-admin")
    monkeypatch.setenv("ADMIN_DEFAULT_PASSWORD", "seed-password")

    with SessionLocal() as db:
        created = ensure_default_admin(db)

    assert created is not None
    assert created.username == "seed-admin"
    assert "default admin user created" in caplog.text.lower()
