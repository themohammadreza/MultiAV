import pytest

from app.core import admin_auth


def test_validate_admin_auth_secret_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADMIN_AUTH_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="ADMIN_AUTH_SECRET must be set"):
        admin_auth.validate_admin_auth_secret()


def test_validate_admin_auth_secret_too_short(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_AUTH_SECRET", "short-secret")
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        admin_auth.validate_admin_auth_secret()


def test_validate_admin_auth_secret_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_AUTH_SECRET", "strong-secret-value-with-32-characters")
    admin_auth.validate_admin_auth_secret()
