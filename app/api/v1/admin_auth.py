from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app.core.admin_auth import (
    ADMIN_AUTH_COOKIE_NAME,
    ADMIN_AUTH_COOKIE_SECURE,
    ADMIN_AUTH_TTL_SECONDS,
    AdminSession,
    create_admin_token,
    get_admin_session,
    validate_admin_credentials,
)


router = APIRouter()


class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class AdminLoginResponse(BaseModel):
    token: str
    expires_at: datetime


class AdminMeResponse(BaseModel):
    username: str
    expires_at: datetime | None = None


@router.post("/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest, response: Response):
    validate_admin_credentials(payload.username, payload.password)
    token, expires_at = create_admin_token(payload.username)
    response.set_cookie(
        ADMIN_AUTH_COOKIE_NAME,
        token,
        httponly=True,
        secure=ADMIN_AUTH_COOKIE_SECURE,
        samesite="lax",
        max_age=ADMIN_AUTH_TTL_SECONDS,
    )
    return AdminLoginResponse(token=token, expires_at=expires_at)


@router.post("/logout")
def admin_logout(response: Response):
    response.delete_cookie(ADMIN_AUTH_COOKIE_NAME)
    return {"ok": True}


@router.get("/me", response_model=AdminMeResponse)
def admin_me(session: AdminSession = Depends(get_admin_session)):
    return AdminMeResponse(username=session.username, expires_at=session.expires_at)
