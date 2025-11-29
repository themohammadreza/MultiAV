from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.storage import save_file
from app.db.session import SessionLocal
from app.db.models import File as FileModel, ScanJob
from app.workers.tasks import run_scan
import hashlib
from uuid import uuid4

router = APIRouter()

@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    sha256, path = await save_file(file)

    db = SessionLocal()

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

    db.close()

    return {"job.id": job.id,
            "status": "queued"}

