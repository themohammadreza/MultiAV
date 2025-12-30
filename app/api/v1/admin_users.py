from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.admin_auth import AdminSession, get_admin_session
from app.core.security import hash_password, verify_password
from app.db.models import AdminUser
from app.db.session import get_db


router = APIRouter()


class AdminUserResponse(BaseModel):
    id: str
    username: str
    is_superadmin: bool
    is_active: bool
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
    current_password: str | None = Field(default=None, min_length=1, max_length=255)
    is_superadmin: bool | None = None
    is_active: bool | None = None


def _require_superadmin(session: AdminSession) -> None:
    if not session.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin privileges required")


def _to_response(user: AdminUser) -> AdminUserResponse:
    return AdminUserResponse(
        id=str(user.id),
        username=user.username,
        is_superadmin=user.is_superadmin,
        is_active=user.is_active,
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


def _active_superadmin_count(db: Session, exclude_user_id: UUID | None = None) -> int:
    query = db.query(AdminUser).filter(
        AdminUser.is_superadmin.is_(True),
        AdminUser.is_active.is_(True),
    )
    if exclude_user_id is not None:
        query = query.filter(AdminUser.id != exclude_user_id)
    return query.count()


def _ensure_active_superadmin_remains(db: Session, user: AdminUser, new_is_superadmin: bool, new_is_active: bool) -> None:
    if new_is_superadmin and new_is_active:
        return
    if user.is_superadmin and user.is_active:
        if _active_superadmin_count(db, exclude_user_id=user.id) <= 0:
            raise HTTPException(status_code=400, detail="At least one superadmin must remain active")


@router.get("/me/", response_model=AdminUserResponse)
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


@router.patch("/{user_id}/", response_model=AdminUserResponse)
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
        if user.id == session.user_id:
            if payload.current_password is None:
                raise HTTPException(status_code=400, detail="Current password is required to update your password")
            if not verify_password(payload.current_password, user.password_hash):
                raise HTTPException(status_code=400, detail="Current password is incorrect")
        user.password_hash = hash_password(payload.password)
        changed = True

    if payload.is_superadmin is not None and payload.is_superadmin != user.is_superadmin:
        if user.is_superadmin and not payload.is_superadmin:
            _ensure_active_superadmin_remains(db, user, False, user.is_active)
        user.is_superadmin = payload.is_superadmin
        changed = True

    if payload.is_active is not None and payload.is_active != user.is_active:
        if user.id == session.user_id and payload.is_active is False:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        _ensure_active_superadmin_remains(db, user, user.is_superadmin, payload.is_active)
        user.is_active = payload.is_active
        changed = True

    if not changed:
        raise HTTPException(status_code=400, detail="No changes requested")

    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_response(user)


@router.delete("/{user_id}/")
def delete_admin_user(
    user_id: str,
    session: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    _require_superadmin(session)
    user = _get_user_or_404(db, user_id)
    if user.is_superadmin:
        if user.is_active and _active_superadmin_count(db, exclude_user_id=user.id) <= 0:
            raise HTTPException(status_code=400, detail="At least one superadmin must remain active")
    db.delete(user)
    db.commit()
    return {"ok": True}
