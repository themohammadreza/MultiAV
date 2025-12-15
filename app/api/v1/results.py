from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_api_key
from app.core.config import settings
from app.core.rate_limit import check_rate_limit, get_rate_limit_redis_client
from app.db.models import APIKey as APIKeyModel, ScanJob
from app.db.session import get_db
from app.services.aggregator.summary import summarize_job

router = APIRouter()

NOT_FOUND_MESSAGE = (
    "Job not found. Make sure you scanned a file via /api/v1/scan and copied the full job_id."
)

@router.get(
    "/{job_id}",
    responses={
        404: {
            "description": NOT_FOUND_MESSAGE,
            "content": {
                "application/json": {"example": {"detail": NOT_FOUND_MESSAGE}}
            },
        }
    },
)
def get_results(
    job_id: str,
    api_key: APIKeyModel = Depends(get_current_api_key),
    db: Session = Depends(get_db),
):
    redis_client = get_rate_limit_redis_client(settings.REDIS_URL)
    check_rate_limit(api_key, redis_client)

    try:
        job_uuid = UUID(job_id)
    except ValueError:
        # Match behavior of a missing job instead of leaking DB errors
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    job = db.query(ScanJob).filter(ScanJob.id == job_uuid).first()
    
    if not job:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    # Sort results for stable output (oldest first)
    engine_results = sorted(
        job.results,
        key=lambda r: r.scanned_at or job.created_at,
    )

    return summarize_job(job, engine_results)
