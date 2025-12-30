from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.admin_auth import AdminSession, get_admin_session
from app.db.models import APIKey as APIKeyModel, ApiKeyAuditLog, ApiKeyUsage, ScanJob
from app.db.session import get_db


router = APIRouter()


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    rate_limit_per_day: int | None = Field(default=None, ge=0, le=100000)


class ApiKeyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    rate_limit_per_day: int | None = Field(default=None, ge=0, le=100000)
    is_active: bool | None = None
    rotate: bool = False


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    rate_limit_per_day: int
    created_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None
    is_active: bool
    raw_key: str | None = None


class ApiKeyScanItem(BaseModel):
    job_id: str
    status: str
    verdict: str | None = None
    created_at: datetime


class ApiKeyScansResponse(BaseModel):
    items: list[ApiKeyScanItem]
    count: int
    total: int


class ApiKeyAuditItem(BaseModel):
    id: str
    action: str
    performed_by_username: str
    created_at: datetime
    metadata: dict | None = None


class ApiKeyAuditResponse(BaseModel):
    items: list[ApiKeyAuditItem]
    count: int
    total: int


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _generate_key() -> tuple[str, str]:
    raw_key = secrets.token_urlsafe(32)
    return raw_key, _hash_key(raw_key)


def _get_key_or_404(db: Session, key_id: str) -> APIKeyModel:
    try:
        key_uuid = UUID(key_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="API key not found")

    key = db.query(APIKeyModel).filter(APIKeyModel.id == key_uuid).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    return key


def _log_audit_entry(
    db: Session,
    *,
    api_key_id: UUID,
    action: str,
    admin: AdminSession,
    metadata: dict | None = None,
) -> None:
    db.add(
        ApiKeyAuditLog(
            api_key_id=api_key_id,
            action=action,
            performed_by_admin_id=admin.user_id,
            performed_by_username=admin.username,
            metadata_json=metadata,
        )
    )


@router.get("/", response_model=list[ApiKeyResponse])
def list_keys(
    _: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    keys = db.query(APIKeyModel).order_by(APIKeyModel.created_at.desc()).all()
    return [
        ApiKeyResponse(
            id=str(key.id),
            name=key.name,
            rate_limit_per_day=int(key.rate_limit_per_day or 0),
            created_at=key.created_at,
            revoked_at=key.revoked_at,
            last_used_at=key.last_used_at,
            is_active=key.is_active,
        )
        for key in keys
    ]


@router.post("/", response_model=ApiKeyResponse)
def create_key(
    payload: ApiKeyCreateRequest,
    admin: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    raw_key, key_hash = _generate_key()
    rate_limit = payload.rate_limit_per_day
    if rate_limit is None:
        rate_limit = 60
    now = datetime.now(timezone.utc)

    api_key = APIKeyModel(
        name=payload.name.strip(),
        key_hash=key_hash,
        rate_limit_per_day=rate_limit,
        created_at=now,
        revoked_at=None,
        last_used_at=None,
        is_active=True,
    )
    db.add(api_key)
    db.flush()
    _log_audit_entry(
        db,
        api_key_id=api_key.id,
        action="create",
        admin=admin,
        metadata={"name": api_key.name, "rate_limit_per_day": api_key.rate_limit_per_day},
    )
    db.commit()
    db.refresh(api_key)

    return ApiKeyResponse(
        id=str(api_key.id),
        name=api_key.name,
        rate_limit_per_day=int(api_key.rate_limit_per_day or 0),
        created_at=api_key.created_at,
        revoked_at=api_key.revoked_at,
        last_used_at=api_key.last_used_at,
        is_active=api_key.is_active,
        raw_key=raw_key,
    )


@router.patch("/{key_id}/", response_model=ApiKeyResponse)
def update_key(
    key_id: str,
    payload: ApiKeyUpdateRequest,
    admin: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    key = _get_key_or_404(db, key_id)
    changed = False
    old_name = key.name
    old_rate_limit = key.rate_limit_per_day

    if payload.name is not None:
        key.name = payload.name.strip()
        changed = True

    if payload.rate_limit_per_day is not None:
        key.rate_limit_per_day = payload.rate_limit_per_day
        changed = True

    if payload.is_active is not None and payload.is_active != key.is_active:
        key.is_active = payload.is_active
        if key.is_active:
            key.revoked_at = None
        else:
            key.revoked_at = datetime.now(timezone.utc)
        changed = True

    raw_key = None
    if payload.rotate:
        raw_key, key_hash = _generate_key()
        key.key_hash = key_hash
        key.created_at = datetime.now(timezone.utc)
        key.revoked_at = None
        key.last_used_at = None
        key.is_active = True
        changed = True

    if not changed:
        raise HTTPException(status_code=400, detail="No changes requested")

    action = "rotate" if payload.rotate else "update"
    metadata: dict[str, object] = {}
    if payload.name is not None:
        metadata["old_name"] = old_name
        metadata["new_name"] = key.name
    if payload.rate_limit_per_day is not None:
        metadata["old_rate_limit_per_day"] = old_rate_limit
        metadata["new_rate_limit_per_day"] = key.rate_limit_per_day
    if payload.rotate:
        metadata["rotated"] = True
    if payload.is_active is not None:
        metadata["is_active"] = key.is_active
        metadata["revoked_at"] = key.revoked_at.isoformat() if key.revoked_at else None

    db.add(key)
    _log_audit_entry(
        db,
        api_key_id=key.id,
        action=action,
        admin=admin,
        metadata=metadata or None,
    )
    db.commit()
    db.refresh(key)

    return ApiKeyResponse(
        id=str(key.id),
        name=key.name,
        rate_limit_per_day=int(key.rate_limit_per_day or 0),
        created_at=key.created_at,
        revoked_at=key.revoked_at,
        last_used_at=key.last_used_at,
        is_active=key.is_active,
        raw_key=raw_key,
    )


@router.post("/{key_id}/revoke/", response_model=ApiKeyResponse)
def revoke_key(
    key_id: str,
    admin: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    key = _get_key_or_404(db, key_id)
    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
        key.is_active = False
        db.add(key)
        _log_audit_entry(
            db,
            api_key_id=key.id,
            action="revoke",
            admin=admin,
            metadata={"revoked_at": key.revoked_at.isoformat()},
        )
        db.commit()
        db.refresh(key)

    return ApiKeyResponse(
        id=str(key.id),
        name=key.name,
        rate_limit_per_day=int(key.rate_limit_per_day or 0),
        created_at=key.created_at,
        revoked_at=key.revoked_at,
        last_used_at=key.last_used_at,
        is_active=key.is_active,
    )


@router.delete("/{key_id}/")
def delete_key(
    key_id: str,
    _: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    key = _get_key_or_404(db, key_id)
    db.query(ScanJob).filter(ScanJob.api_key_id == key.id).update(
        {ScanJob.api_key_id: None}, synchronize_session=False
    )
    db.query(ApiKeyUsage).filter(ApiKeyUsage.api_key_id == key.id).delete(synchronize_session=False)
    db.query(ApiKeyAuditLog).filter(ApiKeyAuditLog.api_key_id == key.id).delete(synchronize_session=False)
    db.delete(key)
    db.commit()
    return {"ok": True}


@router.get("/{key_id}/scans/", response_model=ApiKeyScansResponse)
def list_key_scans(
    key_id: str,
    _: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    key = _get_key_or_404(db, key_id)
    base_query = db.query(ApiKeyUsage).filter(ApiKeyUsage.api_key_id == key.id)
    total = base_query.count()

    scans = (
        base_query.order_by(ApiKeyUsage.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        ApiKeyScanItem(
            job_id=str(scan.job_id),
            status=scan.status,
            verdict=scan.verdict,
            created_at=scan.created_at,
        )
        for scan in scans
    ]
    return ApiKeyScansResponse(items=items, count=len(items), total=total)


@router.get("/{key_id}/audit", response_model=ApiKeyAuditResponse)
def list_key_audit_logs(
    key_id: str,
    _: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    key = _get_key_or_404(db, key_id)
    base_query = db.query(ApiKeyAuditLog).filter(ApiKeyAuditLog.api_key_id == key.id)
    total = base_query.count()

    logs = (
        base_query.order_by(ApiKeyAuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        ApiKeyAuditItem(
            id=str(log.id),
            action=log.action,
            performed_by_username=log.performed_by_username,
            created_at=log.created_at,
            metadata=log.metadata_json,
        )
        for log in logs
    ]
    return ApiKeyAuditResponse(items=items, count=len(items), total=total)
