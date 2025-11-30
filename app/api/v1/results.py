from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import ScanJob

router = APIRouter()

@router.get("/{job_id}")
def get_results(job_id: str, db: Session = Depends(get_db)):
    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    
    if not job:
        raise HTTPException(status_code = 404, details = "Job not found!")

    return {
        "job_id": str(job.id),
        "status": job.status,
        "result": [r.result for r in job.results]
    }
