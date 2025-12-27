import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

import app.services.storage as storage


@pytest.mark.unit
def test_ensure_local_copy_raises_for_missing_local_file():
    svc = storage.StorageService.__new__(storage.StorageService)
    svc.backend = "local"

    with pytest.raises(FileNotFoundError):
        svc.ensure_local_copy("/nonexistent/file.bin")


@pytest.mark.unit
def test_ensure_local_copy_uses_existing_local_when_s3_missing(tmp_path):
    dummy_file = tmp_path / "existing.bin"
    dummy_file.write_bytes(b"data")

    svc = storage.StorageService.__new__(storage.StorageService)
    svc.backend = "s3"
    svc.bucket = "bucket"
    svc.base_path = tmp_path
    svc._client = Mock()

    # Simulate S3 download failure but local fallback
    svc._client.download_fileobj.side_effect = Exception("download failed")

    local_path, cleanup = svc.ensure_local_copy(str(dummy_file))

    assert Path(local_path).exists()
    cleanup()


@pytest.mark.unit
def test_ensure_local_copy_downloads_when_remote_exists(tmp_path):
    svc = storage.StorageService.__new__(storage.StorageService)
    svc.backend = "s3"
    svc.bucket = "bucket"
    svc.base_path = tmp_path

    def _write_remote(bucket, key, fileobj):  # noqa: ANN001 - mock signature
        fileobj.write(b"from-remote")

    svc._client = Mock()
    svc._client.download_fileobj.side_effect = _write_remote

    path, cleanup = svc.ensure_local_copy("remote/key")

    assert Path(path).exists()
    assert Path(path).read_bytes() == b"from-remote"
    cleanup()


@pytest.mark.unit
def test_save_file_delegates_to_service(monkeypatch):
    calls = {}

    class DummyService:
        async def save_file(self, upload):  # noqa: ANN001 - test double
            calls["called_with"] = upload
            return "digest", "location"

    monkeypatch.setattr(storage, "get_storage_service", lambda: DummyService())

    result = asyncio.run(storage.save_file("payload"))

    assert result == ("digest", "location")
    assert calls["called_with"] == "payload"


@pytest.mark.unit
def test_schedule_ttl_cleanup_replaces_existing_timer(monkeypatch):
    class FakeTimer:
        def __init__(self, interval, func):  # noqa: ANN001 - signature matches threading.Timer
            self.interval = interval
            self.func = func
            self.started = False
            self.cancelled = False

        def start(self):
            self.started = True

        def cancel(self):
            self.cancelled = True

        def is_alive(self):
            return self.started and not self.cancelled

    created: list[FakeTimer] = []

    def fake_timer(interval, func):  # noqa: ANN001 - test double
        timer = FakeTimer(interval, func)
        created.append(timer)
        return timer

    svc = storage.StorageService.__new__(storage.StorageService)
    svc.backend = "s3"
    svc.object_ttl_seconds = 5
    svc._cleanup_bucket = lambda: None  # noqa: E731 - simple stub
    existing = FakeTimer(10, lambda: None)
    existing.start()
    svc._cleanup_timer = existing

    monkeypatch.setattr(storage.threading, "Timer", fake_timer)

    svc._schedule_ttl_cleanup()

    assert existing.cancelled is True
    assert created, "A new cleanup timer should be scheduled"
    assert created[0].started is True
    assert svc._cleanup_timer is created[0]


@pytest.mark.unit
def test_cleanup_bucket_batches_ttl_deletions():
    class FakePaginator:
        def __init__(self, pages):
            self.pages = pages

        def paginate(self, Bucket):  # noqa: N802 - boto3 signature
            return self.pages

    class FakeClient:
        def __init__(self, pages):
            self.pages = pages

        def get_paginator(self, name):
            assert name == "list_objects_v2"
            return FakePaginator(self.pages)

    svc = storage.StorageService.__new__(storage.StorageService)
    svc.backend = "s3"
    svc.bucket = "bucket"
    svc.object_ttl_seconds = 10
    svc.max_bucket_bytes = 10**9

    now = datetime.now(timezone.utc)
    total_objects = 2500
    per_page = 500
    pages = []
    for start in range(0, total_objects, per_page):
        contents = [
            {
                "Key": f"old-{idx}",
                "LastModified": now - timedelta(seconds=20),
                "Size": 1,
            }
            for idx in range(start, start + per_page)
        ]
        pages.append({"Contents": contents})

    svc._client = FakeClient(pages)
    deleted_batches: list[list[str]] = []
    svc._delete_objects = lambda keys: deleted_batches.append(list(keys))

    svc._cleanup_bucket()

    deleted_keys = [key for batch in deleted_batches for key in batch]
    assert len(deleted_keys) == total_objects
    assert all(len(batch) <= storage.DELETE_BATCH_SIZE for batch in deleted_batches)


@pytest.mark.unit
def test_cleanup_bucket_prunes_oldest_for_max_bytes():
    class FakePaginator:
        def __init__(self, pages):
            self.pages = pages

        def paginate(self, Bucket):  # noqa: N802 - boto3 signature
            return self.pages

    class FakeClient:
        def __init__(self, pages):
            self.pages = pages

        def get_paginator(self, name):
            assert name == "list_objects_v2"
            return FakePaginator(self.pages)

    svc = storage.StorageService.__new__(storage.StorageService)
    svc.backend = "s3"
    svc.bucket = "bucket"
    svc.object_ttl_seconds = 3600
    svc.max_bucket_bytes = 500

    now = datetime.now(timezone.utc)
    objects = [
        {
            "Key": f"obj-{idx}",
            "LastModified": now - timedelta(seconds=idx),
            "Size": 100,
        }
        for idx in range(10)
    ]
    pages = [{"Contents": objects[:5]}, {"Contents": objects[5:]}]
    svc._client = FakeClient(pages)

    deleted_batches: list[list[str]] = []
    svc._delete_objects = lambda keys: deleted_batches.append(list(keys))

    svc._cleanup_bucket()

    deleted_keys = [key for batch in deleted_batches for key in batch]
    expected_keys = {
        item["Key"]
        for item in sorted(objects, key=lambda item: item["LastModified"])[:5]
    }
    assert set(deleted_keys) == expected_keys
