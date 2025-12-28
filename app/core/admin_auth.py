from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.admin_seed import ensure_default_admin
from app.core.security import verify_password
from app.db.models import AdminUser
from app.db.session import get_db

ADMIN_AUTH_COOKIE_NAME = "admin_session"
ADMIN_AUTH_TTL_SECONDS = int(os.getenv("ADMIN_AUTH_TTL_SECONDS", "3600"))
ADMIN_AUTH_SECRET = os.getenv("ADMIN_AUTH_SECRET", "change-me")
ADMIN_AUTH_COOKIE_SECURE = os.getenv("ADMIN_AUTH_COOKIE_SECURE", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


@dataclass(frozen=True)
class AdminSession:
    user_id: UUID
    username: str
    is_superadmin: bool
    expires_at: datetime | None


def _bypass_enabled() -> bool:
    return os.getenv("BYPASS_AUTH", "").strip().lower() in {"1", "true", "yes", "on"}


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _get_secret_bytes() -> bytes:
    return ADMIN_AUTH_SECRET.encode("utf-8")


def create_admin_token(user: AdminUser) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ADMIN_AUTH_TTL_SECONDS)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_encoded = _b64encode(payload_bytes)
    signature = hmac.new(_get_secret_bytes(), payload_encoded.encode("utf-8"), hashlib.sha256).digest()
    token = f"{payload_encoded}.{_b64encode(signature)}"
    return token, expires_at


def verify_admin_token(token: str) -> tuple[UUID, datetime]:
    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid admin session")

    expected_signature = hmac.new(
        _get_secret_bytes(), payload_part.encode("utf-8"), hashlib.sha256
    ).digest()
    if not secrets.compare_digest(_b64encode(expected_signature), signature_part):
        raise HTTPException(status_code=401, detail="Invalid admin session")

    try:
        payload = json.loads(_b64decode(payload_part))
    except json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="Invalid admin session")

    user_id_value = payload.get("sub")
    exp = payload.get("exp")
    if not isinstance(user_id_value, str) or not user_id_value:
        raise HTTPException(status_code=401, detail="Invalid admin session")
    if not isinstance(exp, int):
        raise HTTPException(status_code=401, detail="Invalid admin session")

    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Admin session expired")

    try:
        user_id = UUID(user_id_value)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid admin session")

    return user_id, expires_at


def validate_admin_credentials(db: Session, username: str, password: str) -> AdminUser:
    if _bypass_enabled():
        admin = db.query(AdminUser).filter(AdminUser.username == username).first()
        if admin:
            return admin

    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if not admin or not verify_password(password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    return admin


def get_admin_session(
    request: Request,
    db: Session = Depends(get_db),
) -> AdminSession:
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header:
        scheme, _, value = auth_header.partition(" ")
        if scheme.lower() == "bearer" and value:
            token = value.strip()

    if not token:
        token = request.cookies.get(ADMIN_AUTH_COOKIE_NAME)

    if not token:
        raise HTTPException(status_code=401, detail="Missing admin session")

    if _bypass_enabled():
        admin = db.query(AdminUser).order_by(AdminUser.created_at.asc()).first()
        if not admin:
            admin = ensure_default_admin(db)
        if not admin:
            raise HTTPException(status_code=401, detail="Missing admin session")
        return AdminSession(
            user_id=admin.id,
            username=admin.username,
            is_superadmin=admin.is_superadmin,
            expires_at=None,
        )

    user_id, expires_at = verify_admin_token(token)
    admin = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid admin session")
    return AdminSession(
        user_id=admin.id,
        username=admin.username,
        is_superadmin=admin.is_superadmin,
        expires_at=expires_at,
    )
