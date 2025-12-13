from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload

from app.db.models import File, ScanJob
from app.db.session import get_db
from app.services.aggregator.summary import summarize_job
from app.services.orchestrator.registry import get_active_engines

router = APIRouter()


@router.get("/jobs/recent")
def list_recent_jobs(
    *,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="Filter by status substring"),
    sha256: Optional[str] = Query(None, description="Filter by SHA256 substring"),
):
    query = (
        db.query(ScanJob)
        .join(File)
        .options(selectinload(ScanJob.file), selectinload(ScanJob.results))
        .order_by(ScanJob.created_at.desc())
    )

    if status:
        query = query.filter(ScanJob.status.ilike(f"%{status}%"))
    if sha256:
        query = query.filter(File.sha256.ilike(f"%{sha256}%"))

    jobs: List[ScanJob] = query.limit(limit).all()

    items = []
    for job in jobs:
        summary = summarize_job(
            job,
            sorted(job.results, key=lambda r: r.scanned_at or job.created_at),
        )
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

    return {"items": items, "count": len(items)}


@router.get("/engines/active")
def get_engines():
    registry = get_active_engines()
    engines = [
        {"engine": name, "timeout": meta.get("timeout"), "weight": meta.get("weight")}
        for name, meta in sorted(registry.items())
    ]
    return {"engines": engines}
