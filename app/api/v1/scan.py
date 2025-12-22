from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
import hashlib
from uuid import uuid4
from datetime import datetime, timezone
import pytz

from app.services.storage import compute_sha256, save_file
from app.db.session import get_db
from app.db.models import APIKey as APIKeyModel, File as FileModel, ScanJob
from app.workers.tasks import run_scan

from app.core.config import settings
from app.core.auth import get_current_api_key
from app.core.rate_limit import check_rate_limit, get_rate_limit_redis_client


router = APIRouter()

@router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    api_key: APIKeyModel | None = Depends(get_current_api_key),
    db: Session = Depends(get_db),
):
    redis_client = get_rate_limit_redis_client(settings.REDIS_URL)

    sha256 = await compute_sha256(file)

    iran_tz = pytz.timezone('Asia/Tehran')

    # check cache
    existing = db.query(FileModel).filter(FileModel.sha256 == sha256).first()
    file_entry: FileModel | None = existing
    if existing:
        latest_job_query = db.query(ScanJob).filter(ScanJob.file_id == existing.id)
        if api_key:
            latest_job_query = latest_job_query.filter(ScanJob.api_key_id == api_key.id)
        else:
            latest_job_query = latest_job_query.filter(ScanJob.api_key_id.is_(None))
        latest_job = latest_job_query.order_by(ScanJob.created_at.desc()).first()

        if latest_job:
            # Convert UTC to Tehran time
            first_scan = existing.uploaded_at.astimezone(iran_tz)

            return {
                "job_id": latest_job.id,
                "status": latest_job.status,
                "cached": True,
                "scanned_at": first_scan.isoformat(),
            }

    check_rate_limit(api_key, redis_client)
    _, location = await save_file(file)

    # if it's a new file
    if not file_entry:
        file_entry = FileModel(
            sha256 = sha256,
            path = location,
        )
        db.add(file_entry)
        db.commit()
        db.refresh(file_entry)

    
    job = ScanJob(
        file_id=file_entry.id,
        api_key_id=api_key.id if api_key else None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    run_scan.delay(str(job.id), location)

    return {"job_id": str(job.id),
            "status": "queued",
            "cached": False,
            }

# Accept the route without a trailing slash to avoid redirects (important behind proxies).
@router.post("", include_in_schema=False)
async def upload_file_no_trailing(
    file: UploadFile = File(...),
    api_key: APIKeyModel | None = Depends(get_current_api_key),
    db: Session = Depends(get_db),
):
    return await upload_file(file=file, api_key=api_key, db=db)
