from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import ScanJob
from app.db.session import get_db

router = APIRouter()

@router.get("/{job_id}")
def get_results(job_id: str, db: Session = Depends(get_db)):
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        # Match behavior of a missing job instead of leaking DB errors
        raise HTTPException(status_code=404, detail="Job not found!")

    job = db.query(ScanJob).filter(ScanJob.id == job_uuid).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found!")

    return {
        "job_id": str(job.id),
        "status": job.status,
        "result": [r.result for r in job.results]
    }
