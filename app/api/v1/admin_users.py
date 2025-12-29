from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.admin_auth import AdminSession, get_admin_session
from app.core.security import hash_password
from app.db.models import AdminUser
from app.db.session import get_db


router = APIRouter()


class AdminUserResponse(BaseModel):
    id: str
    username: str
    is_superadmin: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


class AdminUserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)
    is_superadmin: bool = False


class AdminUserUpdateRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=1, max_length=255)
    is_superadmin: bool | None = None


def _require_superadmin(session: AdminSession) -> None:
    if not session.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin privileges required")


def _to_response(user: AdminUser) -> AdminUserResponse:
    return AdminUserResponse(
        id=str(user.id),
        username=user.username,
        is_superadmin=user.is_superadmin,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )


def _get_user_or_404(db: Session, user_id: str) -> AdminUser:
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Admin user not found")

    user = db.query(AdminUser).filter(AdminUser.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="Admin user not found")
    return user


@router.get("/me", response_model=AdminUserResponse)
def get_my_admin_profile(
    session: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, str(session.user_id))
    return _to_response(user)


@router.get("/", response_model=list[AdminUserResponse])
def list_admin_users(
    session: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    _require_superadmin(session)
    users = db.query(AdminUser).order_by(AdminUser.created_at.asc()).all()
    return [_to_response(user) for user in users]


@router.post("/", response_model=AdminUserResponse)
def create_admin_user(
    payload: AdminUserCreateRequest,
    session: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    _require_superadmin(session)
    username = payload.username.strip()
    if db.query(AdminUser).filter(AdminUser.username == username).first():
        raise HTTPException(status_code=409, detail="Username already exists")

    user = AdminUser(
        username=username,
        password_hash=hash_password(payload.password),
        is_superadmin=payload.is_superadmin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_response(user)


@router.patch("/{user_id}", response_model=AdminUserResponse)
def update_admin_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    session: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    _require_superadmin(session)
    user = _get_user_or_404(db, user_id)
    changed = False

    if payload.username is not None:
        username = payload.username.strip()
        if username != user.username:
            if db.query(AdminUser).filter(AdminUser.username == username).first():
                raise HTTPException(status_code=409, detail="Username already exists")
            user.username = username
            changed = True

    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
        changed = True

    if payload.is_superadmin is not None and payload.is_superadmin != user.is_superadmin:
        if user.is_superadmin and not payload.is_superadmin:
            superadmin_count = db.query(AdminUser).filter(AdminUser.is_superadmin.is_(True)).count()
            if superadmin_count <= 1:
                raise HTTPException(status_code=400, detail="At least one superadmin must remain")
        user.is_superadmin = payload.is_superadmin
        changed = True

    if not changed:
        raise HTTPException(status_code=400, detail="No changes requested")

    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_response(user)


@router.delete("/{user_id}")
def delete_admin_user(
    user_id: str,
    session: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    _require_superadmin(session)
    user = _get_user_or_404(db, user_id)
    if user.is_superadmin:
        superadmin_count = db.query(AdminUser).filter(AdminUser.is_superadmin.is_(True)).count()
        if superadmin_count <= 1:
            raise HTTPException(status_code=400, detail="At least one superadmin must remain")
    db.delete(user)
    db.commit()
    return {"ok": True}
