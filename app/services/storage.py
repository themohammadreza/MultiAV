import hashlib
import logging
import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable, Optional, Tuple

import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024


class StorageService:
    def __init__(self) -> None:
        self.backend = settings.STORAGE_BACKEND
        self.base_path = Path(settings.STORAGE_PATH)

        if self.backend == "s3":
            if not settings.STORAGE_S3_BUCKET:
                raise ValueError("STORAGE_S3_BUCKET must be set when using S3 backend")

            session = boto3.session.Session(
                aws_access_key_id=settings.STORAGE_S3_ACCESS_KEY,
                aws_secret_access_key=settings.STORAGE_S3_SECRET_KEY,
                region_name=settings.STORAGE_S3_REGION,
            )
            self._client = session.client(
                "s3",
                endpoint_url=settings.STORAGE_S3_ENDPOINT,
                use_ssl=settings.STORAGE_S3_USE_SSL,
            )
            self.bucket = settings.STORAGE_S3_BUCKET
            self._ensure_bucket()
        elif self.backend == "local":
            self._client = None
            self.bucket = None
            self.base_path.mkdir(parents=True, exist_ok=True)
        else:
            raise ValueError(f"Unsupported storage backend: {self.backend}")

    def _object_key(self, sha256: str) -> str:
        return f"{sha256}/original"

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError:
            logger.info("Bucket %s not found, attempting creation", self.bucket)
            try:
                create_kwargs = {"Bucket": self.bucket}
                if settings.STORAGE_S3_REGION:
                    create_kwargs["CreateBucketConfiguration"] = {
                        "LocationConstraint": settings.STORAGE_S3_REGION
                    }
                self._client.create_bucket(**create_kwargs)
            except ClientError as exc:  # noqa: BLE001 - surface bucket provisioning issues
                logger.error("Failed to ensure bucket %s exists: %s", self.bucket, exc)
                raise

    async def save_file(self, upload: UploadFile) -> Tuple[str, str]:
        temp = NamedTemporaryFile(delete=False)
        sha256 = hashlib.sha256()

        try:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break
                sha256.update(chunk)
                temp.write(chunk)

            digest = sha256.hexdigest()
            temp.flush()
            temp.seek(0)

            if self.backend == "s3":
                key = self._object_key(digest)
                extra_args = {}
                if upload.content_type:
                    extra_args["ContentType"] = upload.content_type
                self._client.upload_fileobj(temp, self.bucket, key, ExtraArgs=extra_args)
                location = key
            else:
                dir_path = self.base_path / digest
                dir_path.mkdir(parents=True, exist_ok=True)
                file_path = dir_path / "original"
                with open(file_path, "wb") as destination:
                    shutil.copyfileobj(temp, destination)
                location = str(file_path)

            logger.info("Stored upload %s using backend %s", upload.filename, self.backend)
            return digest, location
        finally:
            temp.close()
            if os.path.exists(temp.name):
                os.unlink(temp.name)
            await upload.seek(0)

    def ensure_local_copy(self, location: str) -> Tuple[str, Callable[[], None]]:
        if self.backend == "s3":
            temp = NamedTemporaryFile(delete=False)
            try:
                self._client.download_fileobj(self.bucket, location, temp)
                temp.flush()
                return temp.name, lambda: self._safe_cleanup(temp.name)
            except Exception as exc:  # noqa: BLE001 - caller must handle download failures
                self._safe_cleanup(temp.name)
                raise exc
        if not Path(location).exists():
            raise FileNotFoundError(f"Local file missing: {location}")
        return location, lambda: None

    def migrate_local_files(self, db_session) -> int:
        if self.backend != "s3":
            return 0

        from app.db.models import File  # Imported here to avoid circular imports

        migrated = 0
        records = db_session.query(File).all()
        for record in records:
            path_value = record.path
            if not path_value:
                continue

            path_obj = Path(path_value)
            if not path_obj.exists():
                # Assume already migrated or unreachable
                continue

            digest = record.sha256 or path_obj.parent.name
            key = self._object_key(digest)

            if not self._object_exists(key):
                self._client.upload_file(str(path_obj), self.bucket, key)
            record.path = key
            migrated += 1

        if migrated:
            db_session.commit()
            logger.info("Migrated %s local files to object storage", migrated)
        return migrated

    def _safe_cleanup(self, file_path: str) -> None:
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except OSError:
            logger.warning("Failed to clean up temp file %s", file_path)

    def _object_exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False


_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


async def save_file(upload: UploadFile) -> Tuple[str, str]:
    service = get_storage_service()
    return await service.save_file(upload)
