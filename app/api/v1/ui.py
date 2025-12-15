from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload

from app.db.models import File, ScanJob
from app.db.session import get_db
from app.services.aggregator.summary import summarize_job
from app.services.orchestrator import registry

router = APIRouter()


@router.get("/jobs/recent")
def list_recent_jobs(
    *,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="Filter by status substring"),
    severity: Optional[str] = Query(None, description="Filter by severity label"),
    sha256: Optional[str] = Query(None, description="Filter by SHA256 substring"),
    job_id: Optional[str] = Query(None, description="Filter by job_id"),
):
    query = (
        db.query(ScanJob)
        .join(File)
        .options(selectinload(ScanJob.file), selectinload(ScanJob.results))
        .order_by(ScanJob.created_at.desc())
    )

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
                "started_at": summary.get("started_at"),
                "completed_at": summary.get("completed_at"),
            }
        )
        if len(items) >= limit:
            break

    return {"items": items, "count": len(items)}


@router.get("/engines/active")
def get_engines():
    engine_registry = registry.get_active_engines()
    engines = [
        {"engine": name, "timeout": meta.get("timeout"), "weight": meta.get("weight")}
        for name, meta in sorted(engine_registry.items())
    ]
    return {"engines": engines}
