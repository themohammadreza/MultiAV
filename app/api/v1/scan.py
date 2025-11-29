from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.storage import save_file
import hashlib
import uuid

router = APIRouter()

@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file.")

    sha256 = hashlib.sha256(contents).hexdigest()
    file_id = str(uuid.uuid4())

    saved_path = save_file(file_id, contents)

    return {
        "file_id": file_id,
        "sha256": sha256,
        "path": saved_path,
        "status": "received"
    }

