import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

botocore_exceptions = pytest.importorskip("botocore.exceptions")
ClientError = botocore_exceptions.ClientError
boto3 = pytest.importorskip("boto3")
mock_s3 = pytest.importorskip("moto").mock_s3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import File, Base
from app.services import storage
from app.services.storage import StorageService


@pytest.fixture(autouse=True)
def reset_storage_service():
    storage._storage_service = None
    yield
    storage._storage_service = None


def test_bucket_creation_skips_location_for_us_east_1(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.create_kwargs = None

        def head_bucket(self, Bucket):  # noqa: N802
            raise ClientError({"Error": {"Code": "404"}}, "HeadBucket")

        def create_bucket(self, **kwargs):
            self.create_kwargs = kwargs

    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("STORAGE_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("STORAGE_S3_REGION", "us-east-1")
    monkeypatch.setattr(storage.settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage.settings, "STORAGE_S3_BUCKET", "test-bucket")
    monkeypatch.setattr(storage.settings, "STORAGE_S3_REGION", "us-east-1")

    fake_client = FakeClient()

    def mock_session(*args, **kwargs):
        class MockSession:
            def client(self, *a, **kw):
                return fake_client

        return MockSession()

    monkeypatch.setattr("boto3.session.Session", mock_session)

    storage_service = StorageService()

    assert storage_service.bucket == "test-bucket"
    assert "CreateBucketConfiguration" not in fake_client.create_kwargs


def test_s3_client_uses_path_style(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.create_kwargs = None

        def head_bucket(self, Bucket):
            raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket")

        def create_bucket(self, **kwargs):
            self.create_kwargs = kwargs

    fake_client = FakeClient()
    captured_kwargs = {}

    def capture_client(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return fake_client

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        def client(self, *args, **kwargs):
            return capture_client(*args, **kwargs)

    monkeypatch.setattr(storage.settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage.settings, "STORAGE_S3_BUCKET", "bucket")
    monkeypatch.setattr(storage.settings, "STORAGE_S3_REGION", "us-east-1")
    monkeypatch.setattr(storage.settings, "STORAGE_S3_ACCESS_KEY", "x")
    monkeypatch.setattr(storage.settings, "STORAGE_S3_SECRET_KEY", "y")
    monkeypatch.setattr(storage.settings, "STORAGE_S3_ENDPOINT", "http://minio:9000")
    monkeypatch.setattr(storage.settings, "STORAGE_S3_USE_SSL", False)

    monkeypatch.setattr(boto3, "session", type("S", (), {"Session": FakeSession}))

    StorageService()

    assert isinstance(captured_kwargs.get("config"), Config)
    assert captured_kwargs["config"].s3.get("addressing_style") == "path"


def test_ensure_local_copy_falls_back_to_existing_local_file():
    svc = StorageService.__new__(StorageService)
    svc.backend = "s3"
    svc.base_path = Path("/tmp")
    svc._client = None
    svc.bucket = "bucket"

    with NamedTemporaryFile(delete=False) as temp:
        temp.write(b"data")
        temp_path = temp.name

    try:
        local_path, cleanup = svc.ensure_local_copy(temp_path)
        assert local_path == temp_path
        cleanup()
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@mock_s3
def test_migrate_local_files_uploads_and_cleans(tmp_path):
    bucket = "bucket"
    region = "us-west-2"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(storage.settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage.settings, "STORAGE_S3_BUCKET", bucket)
    monkeypatch.setattr(storage.settings, "STORAGE_S3_REGION", region)
    monkeypatch.setattr(storage.settings, "STORAGE_S3_ACCESS_KEY", "x")
    monkeypatch.setattr(storage.settings, "STORAGE_S3_SECRET_KEY", "y")
    monkeypatch.setattr(storage.settings, "STORAGE_S3_ENDPOINT", None)
    monkeypatch.setattr(storage.settings, "STORAGE_S3_USE_SSL", False)

    s3 = boto3.client("s3", region_name=region)
    s3.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": region},
    )

    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    file_dir = tmp_path / "abc"
    file_dir.mkdir()
    file_path = file_dir / "original"
    file_path.write_bytes(b"payload")

    record = File(sha256="abc", path=str(file_path))
    session.add(record)
    session.commit()

    service = StorageService()
    migrated = service.migrate_local_files(session)

    session.refresh(record)
    assert migrated == 1
    assert record.path == "abc/original"

    objects = s3.list_objects_v2(Bucket=bucket)
    keys = [item["Key"] for item in objects.get("Contents", [])]
    assert "abc/original" in keys

    assert not file_path.exists()
    monkeypatch.undo()
