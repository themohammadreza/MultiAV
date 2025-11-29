import os, hashlib
from pathlib import Path

STORAGE_DIR = Path("storage/files")

async def save_file(upload):
    data = await upload.read()
    sha256 = hashlib.sha256(data).hexdigest()

    dir_path = STORAGE_DIR / sha256
    dir_path.mkdir(parents=True, exist_ok=True)

    file_path = dir_path / "original"
    file_path.write_bytes(data)

    return sha256, str(file_path)

