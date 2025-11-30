from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
import hashlib
from uuid import uuid4

from app.services.storage import save_file
from app.db.session import get_db
from app.db.models import File as FileModel, ScanJob
from app.workers.tasks import run_scan


router = APIRouter()

@router.post("/")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    sha256, path = await save_file(file)

    # check cache
    existing = db.query(FileModel).filter(FileModel.sha256 == sha256).first()
    if existing:
        latest_job = db.query(ScanJob).filter(
        ScanJob.file_id == existing.id).order_by(ScanJob.created_at.desc()).first()

        return {
            "job_id": latest_job.id,
            "status": latest_job.status,
            "cached": True,
        }

    # if it's a new file
    file_entry = FileModel(
        sha256 = sha256,
        path = path,
    )
    db.add(file_entry)
    db.commit()
    db.refresh(file_entry)

    
    job = ScanJob(file_id = file_entry.id)
    db.add(job)
    db.commit()
    db.refresh(job)

    run_scan.delay(str(job.id), path)

    return {"job.id": str(job.id),
            "status": "queued",
            "cached": False,
            }
