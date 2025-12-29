import os
from datetime import datetime, timedelta, timezone
import math
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.core.auth import get_current_api_key
from app.core.config import settings
from app.core.rate_limit import get_rate_limit_info, get_rate_limit_redis_client
from app.db.models import APIKey as APIKeyModel
from app.db.models import File, ScanJob
from app.db.session import get_db
from app.services.aggregator.summary import summarize_job
from app.services.orchestrator import registry

router = APIRouter()
API_KEY_TTL_DAYS = int(os.getenv("API_KEY_TTL_DAYS", "30"))


@router.get("/api-key/")
def get_api_key_status(
    api_key: APIKeyModel | None = Depends(get_current_api_key),
):
    if api_key is None:
        return {"bypassed": True}

    now = datetime.now(timezone.utc)
    created_at = api_key.created_at or now
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    expires_at = created_at + timedelta(days=API_KEY_TTL_DAYS)
    remaining_seconds = max(0, (expires_at - now).total_seconds())
    days_remaining = int(math.ceil(remaining_seconds / 86400)) if remaining_seconds else 0

    redis_client = get_rate_limit_redis_client(settings.REDIS_URL)
    rate_info = get_rate_limit_info(api_key, redis_client)

    return {
        "name": api_key.name,
        "rate_limit_per_day": api_key.rate_limit_per_day,
        "requests_used_today": rate_info.used if rate_info else 0,
        "requests_remaining_today": rate_info.remaining if rate_info else None,
        "resets_at": rate_info.resets_at.isoformat() if rate_info else None,
        "expires_at": expires_at.isoformat(),
        "days_remaining": days_remaining,
    }


@router.get("/jobs/recent/")
def list_recent_jobs(
    *,
    api_key: APIKeyModel | None = Depends(get_current_api_key),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="Filter by status substring"),
    severity: Optional[str] = Query(None, description="Filter by severity label"),
    sha256: Optional[str] = Query(None, description="Filter by SHA256 substring"),
    job_id: Optional[str] = Query(None, description="Filter by job_id"),
):
    if api_key is None:
        raise HTTPException(status_code=401, detail="Missing api_key")

    query = (
        db.query(ScanJob)
        .join(File)
        .options(selectinload(ScanJob.file), selectinload(ScanJob.results))
        .order_by(ScanJob.created_at.desc())
    )
    query = query.filter(ScanJob.api_key_id == api_key.id)

    job_uuid: UUID | None = None
    if job_id:
        try:
            job_uuid = UUID(str(job_id))
        except ValueError:
            job_uuid = None

    if status:
        query = query.filter(ScanJob.status.ilike(f"%{status}%"))
    if sha256:
        query = query.filter(File.sha256.ilike(f"%{sha256}%"))
    if job_uuid:
        query = query.filter(ScanJob.id == job_uuid)

    # Avoid dialect-specific UUID casting surprises (e.g. SQLite) by applying substring filters in Python.
    fetch_limit = 200 if job_id and not job_uuid else limit
    jobs: List[ScanJob] = query.limit(fetch_limit).all()

    items = []
    for job in jobs:
        if job_id and not job_uuid and str(job_id).lower() not in str(job.id).lower():
            continue

        summary = summarize_job(
            job,
            sorted(job.results, key=lambda r: r.scanned_at or job.created_at),
        )
        if severity and summary.get("severity") != severity:
            continue
        items.append(
            {
                "job_id": str(job.id),
                "status": summary.get("status", job.status),
                "verdict": summary.get("verdict"),
                "severity": summary.get("severity"),
                "sha256": job.file.sha256 if job.file else None,
                "filename": summary.get("filename", job.file.filename if job.file else None),
                "started_at": summary.get("started_at"),
                "completed_at": summary.get("completed_at"),
            }
        )
        if len(items) >= limit:
            break

    return {"items": items, "count": len(items)}


@router.get("/engines/active/")
def get_engines():
    engine_registry = registry.get_active_engines()
    engines = [
        {"engine": name, "timeout": meta.get("timeout"), "weight": meta.get("weight")}
        for name, meta in sorted(engine_registry.items())
    ]
    return {"engines": engines}
