from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import ScanJob
from app.db.session import get_db

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
def get_results(job_id: str, db: Session = Depends(get_db)):
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        # Match behavior of a missing job instead of leaking DB errors
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    job = db.query(ScanJob).filter(ScanJob.id == job_uuid).first()
    
    if not job:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    return {
        "job_id": str(job.id),
        "status": job.status,
        "result": [r.result for r in job.results]
    }
