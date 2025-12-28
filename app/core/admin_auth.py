from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request


ADMIN_AUTH_COOKIE_NAME = "admin_session"
ADMIN_AUTH_TTL_SECONDS = int(os.getenv("ADMIN_AUTH_TTL_SECONDS", "3600"))
ADMIN_AUTH_SECRET = os.getenv("ADMIN_AUTH_SECRET", "change-me")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
ADMIN_AUTH_COOKIE_SECURE = os.getenv("ADMIN_AUTH_COOKIE_SECURE", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


@dataclass(frozen=True)
class AdminSession:
    username: str
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


def create_admin_token(username: str) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ADMIN_AUTH_TTL_SECONDS)
    payload = {
        "sub": username,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_encoded = _b64encode(payload_bytes)
    signature = hmac.new(_get_secret_bytes(), payload_encoded.encode("utf-8"), hashlib.sha256).digest()
    token = f"{payload_encoded}.{_b64encode(signature)}"
    return token, expires_at


def verify_admin_token(token: str) -> AdminSession:
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

    username = payload.get("sub")
    exp = payload.get("exp")
    if not isinstance(username, str) or not username:
        raise HTTPException(status_code=401, detail="Invalid admin session")
    if not isinstance(exp, int):
        raise HTTPException(status_code=401, detail="Invalid admin session")

    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Admin session expired")

    return AdminSession(username=username, expires_at=expires_at)


def validate_admin_credentials(username: str, password: str) -> None:
    if _bypass_enabled():
        return

    if not secrets.compare_digest(username, ADMIN_USERNAME) or not secrets.compare_digest(password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid admin credentials")


def get_admin_session(request: Request) -> AdminSession:
    if _bypass_enabled():
        return AdminSession(username=ADMIN_USERNAME or "admin", expires_at=None)

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

    return verify_admin_token(token)
