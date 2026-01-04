import hashlib
import logging
import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable, Optional, Tuple
from datetime import datetime, timezone
import threading

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - fallback for environments without AWS deps
    boto3 = None

    class ClientError(Exception):
        """Minimal stand-in used when botocore is unavailable."""

    class Config:  # type: ignore[override]
        """Placeholder so references remain resolvable when botocore is absent."""

from fastapi import UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024
DELETE_BATCH_SIZE = 1000


class StorageLimitError(RuntimeError):
    """Raised when an upload exceeds the configured storage limits."""


class StorageService:
    def __init__(self) -> None:
        self.backend = settings.STORAGE_BACKEND
        self.base_path = Path(settings.STORAGE_PATH)
        self.object_ttl_seconds = settings.STORAGE_TTL_SECONDS
        self.max_bucket_bytes = settings.STORAGE_MAX_BYTES
        self._cleanup_timer: Optional[threading.Timer] = None
        self._cleanup_lock = threading.Lock()

        if self.backend == "s3":
            if boto3 is None:
                raise ImportError("boto3 is required for s3 storage backend")
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
                config=Config(
                    s3={
                        # Ensure compatibility with MinIO and other S3-compatible
                        # providers that do not support virtual-hosted style.
                        "addressing_style": "path",
                    }
                ),
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
                region = settings.STORAGE_S3_REGION
                if region and region != "us-east-1":
                    create_kwargs["CreateBucketConfiguration"] = {
                        "LocationConstraint": region
                    }
                self._client.create_bucket(**create_kwargs)
            except ClientError as exc:  # noqa: BLE001 - surface bucket provisioning issues
                logger.error("Failed to ensure bucket %s exists: %s", self.bucket, exc)
                raise

    def check_ready(self) -> None:
        if self.backend == "s3":
            self._client.head_bucket(Bucket=self.bucket)
            return
        if self.backend == "local":
            if not self.base_path.exists():
                raise FileNotFoundError(f"Storage path not found: {self.base_path}")
            if not self.base_path.is_dir():
                raise NotADirectoryError(f"Storage path is not a directory: {self.base_path}")
            return
        raise ValueError(f"Unsupported storage backend: {self.backend}")

    async def save_file(self, upload: UploadFile) -> Tuple[str, str]:
        temp = NamedTemporaryFile(delete=False)
        sha256 = hashlib.sha256()
        total_bytes = 0

        try:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break
                sha256.update(chunk)
                temp.write(chunk)
                total_bytes += len(chunk)

            digest = sha256.hexdigest()
            temp.flush()
            temp.seek(0)

            if self.backend == "s3":
                if total_bytes > self.max_bucket_bytes:
                    raise StorageLimitError(
                        "Upload exceeds storage limit "
                        f"({total_bytes} bytes > {self.max_bucket_bytes} bytes)."
                    )
                key = self._object_key(digest)
                extra_args = {}
                if upload.content_type:
                    extra_args["ContentType"] = upload.content_type
                self._client.upload_fileobj(temp, self.bucket, key, ExtraArgs=extra_args)
                location = key
                self._cleanup_bucket()
                self._schedule_ttl_cleanup()
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
            path_obj = Path(location)
            if path_obj.exists():
                return str(path_obj), lambda: None

            temp = NamedTemporaryFile(delete=False)
            try:
                self._client.download_fileobj(self.bucket, location, temp)
                temp.flush()
                return temp.name, lambda: self._safe_cleanup(temp.name)
            except ClientError as exc:
                self._safe_cleanup(temp.name)
                error_code = exc.response.get("Error", {}).get("Code") if exc.response else None
                if error_code == "NoSuchKey" and path_obj.exists():
                    return str(path_obj), lambda: None
                raise
            except Exception as exc:  # noqa: BLE001 - caller must handle download failures
                self._safe_cleanup(temp.name)
                if path_obj.exists():
                    return str(path_obj), lambda: None
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
        cleanup_paths = []

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
            cleanup_paths.append(path_obj)
            record.path = key
            migrated += 1

        if migrated:
            db_session.commit()
            logger.info("Migrated %s local files to object storage", migrated)
            for path_obj in cleanup_paths:
                self._safe_cleanup(str(path_obj))
                parent = path_obj.parent
                try:
                    parent.rmdir()
                except OSError:
                    # Directory not empty or removal failed; ignore
                    pass
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

    def _cleanup_bucket(self) -> None:
        """Delete objects older than TTL or when total size exceeds max_bytes."""
        if self.backend != "s3":
            return

        try:
            paginator = self._client.get_paginator("list_objects_v2")
            total_size = 0
            ttl_deleted_size = 0
            ttl_delete_queue: list[str] = []
            size_candidates: list[tuple[datetime, str, int]] = []
            now = datetime.now(timezone.utc)

            for page in paginator.paginate(Bucket=self.bucket):
                for obj in page.get("Contents", []):
                    key = obj.get("Key")
                    last_modified = obj.get("LastModified")
                    size = int(obj.get("Size", 0))
                    if not key or not last_modified:
                        continue
                    if isinstance(last_modified, datetime) and last_modified.tzinfo is None:
                        last_modified = last_modified.replace(tzinfo=timezone.utc)
                    total_size += size
                    if not isinstance(last_modified, datetime):
                        continue
                    try:
                        age_seconds = (now - last_modified).total_seconds()
                    except Exception:
                        continue
                    if age_seconds >= self.object_ttl_seconds:
                        ttl_deleted_size += size
                        ttl_delete_queue.append(key)
                        if len(ttl_delete_queue) >= DELETE_BATCH_SIZE:
                            self._delete_objects(ttl_delete_queue)
                            ttl_delete_queue.clear()
                        continue
                    size_candidates.append((last_modified, key, size))

            if ttl_delete_queue:
                self._delete_objects(ttl_delete_queue)
                ttl_delete_queue.clear()

            remaining_size = total_size - ttl_deleted_size
            if remaining_size > self.max_bucket_bytes and size_candidates:
                delete_batch: list[str] = []
                for last_modified, key, size in sorted(
                    size_candidates, key=lambda item: item[0]
                ):
                    if remaining_size <= self.max_bucket_bytes:
                        break
                    delete_batch.append(key)
                    remaining_size -= size
                    if len(delete_batch) >= DELETE_BATCH_SIZE:
                        self._delete_objects(delete_batch)
                        delete_batch.clear()
                if delete_batch:
                    self._delete_objects(delete_batch)
        except Exception as exc:  # noqa: BLE001 - cleanup should not break uploads
            logger.warning("Skipping S3 cleanup due to error: %s", exc)
        finally:
            self._cleanup_timer = None

    def _delete_objects(self, keys: list[str]) -> None:
        for idx in range(0, len(keys), DELETE_BATCH_SIZE):
            batch = keys[idx : idx + DELETE_BATCH_SIZE]
            try:
                self._client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
                )
            except ClientError as exc:
                logger.warning("Failed to delete objects %s: %s", batch, exc)

    def _schedule_ttl_cleanup(self) -> None:
        """Best-effort background cleanup after TTL passes, even if no new uploads arrive."""
        if self.backend != "s3":
            return

        with self._cleanup_lock:
            if self._cleanup_timer:
                try:
                    if self._cleanup_timer.is_alive():
                        self._cleanup_timer.cancel()
                except Exception as exc: # noqa: BLE001 cancellation shouldn't block scheduling
                    logger.warning("Failed to cancel existing cleanup timer: %s", exc)
                finally:
                    self._cleanup_timer = None
            try:
                timer = threading.Timer(self.object_ttl_seconds, self._cleanup_bucket)
                timer.daemon = True
                timer.start()
                self._cleanup_timer = timer
            except Exception as exc:
                logger.warning("Failed to schedule TTL cleanup: %s", exc)


_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


async def save_file(upload: UploadFile) -> Tuple[str, str]:
    service = get_storage_service()
    return await service.save_file(upload)


async def compute_sha256(upload: UploadFile) -> str:
    sha256 = hashlib.sha256()
    try:
        while True:
            chunk = await upload.read(CHUNK_SIZE)
            if not chunk:
                break
            sha256.update(chunk)
        return sha256.hexdigest()
    finally:
        await upload.seek(0)
