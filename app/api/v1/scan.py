from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
import hashlib
from uuid import uuid4
from datetime import datetime, timezone
import pytz

from app.services.storage import compute_sha256, save_file
from app.db.session import get_db
from app.db.models import APIKey as APIKeyModel, ApiKeyUsage, File as FileModel, ScanJob
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
    original_filename = file.filename

    iran_tz = pytz.timezone('Asia/Tehran')

    # check cache
    existing = db.query(FileModel).filter(FileModel.sha256 == sha256).first()
    file_entry: FileModel | None = existing
    if existing:
        if not existing.filename and original_filename:
            existing.filename = original_filename
            db.add(existing)
            db.commit()
            db.refresh(existing)

        latest_job_query = db.query(ScanJob).filter(ScanJob.file_id == existing.id)
        if api_key:
            latest_job_query = latest_job_query.filter(ScanJob.api_key_id == api_key.id)
        else:
            latest_job_query = latest_job_query.filter(ScanJob.api_key_id.is_(None))
        latest_job = latest_job_query.order_by(ScanJob.created_at.desc()).first()

        if latest_job:
            if latest_job.status not in {"error", "done_with_errors"}:
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
            filename = original_filename,
        )
        db.add(file_entry)
        db.commit()
        db.refresh(file_entry)

    
    job = ScanJob(
        file_id=file_entry.id,
        api_key_id=api_key.id if api_key else None,
    )
    db.add(job)
    db.flush()

    if api_key:
        usage_stmt = insert(ApiKeyUsage).values(
            api_key_id=api_key.id,
            job_id=job.id,
            status="queued",
            verdict=None,
            created_at=datetime.now(timezone.utc),
        )
        if db.bind and db.bind.dialect.name == "postgresql":
            usage_stmt = usage_stmt.on_conflict_do_nothing(
                constraint="uq_api_key_usages_key_job"
            )
        else:
            usage_stmt = usage_stmt.on_conflict_do_nothing(
                index_elements=[ApiKeyUsage.api_key_id, ApiKeyUsage.job_id]
            )
        db.execute(usage_stmt)

    db.commit()
    db.refresh(job)

    run_scan.delay(str(job.id), location)

    return {"job_id": str(job.id),
            "status": "queued",
            "cached": False,
            }
