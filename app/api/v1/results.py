from fastapi import APIRouter
from app.db.session import SessionLocal
from app.db.models import ScanJob

router = APIRouter()

@router.get("/{file_id}")
def get_results(job_id: str):
    db = SessionLocal()
    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    
    if not job:
        return {"error": "job not found!"}

    return {
        "job_id": job.id,
        "status": job.status,
        "result": [r.result for r in job.results]
    }

