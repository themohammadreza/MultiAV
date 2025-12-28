import pytest

# Test samples are generated at runtime to avoid storing binary fixtures in the
# repository while still providing common EICAR and clean-file content across
# unit suites.
@pytest.fixture
def eicar_file(tmp_path):
    """EICAR test file that all AVs should detect"""
    f = tmp_path / "eicar.txt"
    f.write_text("X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*")
    return f


@pytest.fixture
def clean_file(tmp_path):
    """Clean file that should not trigger detections"""
    f = tmp_path / "clean.txt"
    f.write_text("Hello, world!")
    return f
import asyncio
import httpx
import os
import shutil
import sys
import tempfile
from typing import Generator
import types

import pytest

# Configure disposable local resources before application modules import settings
_db_fd, _db_path = tempfile.mkstemp(prefix="multiav-test-db-", suffix=".sqlite")
os.close(_db_fd)
_storage_dir = tempfile.mkdtemp(prefix="multiav-storage-")

sys.path.insert(0, os.path.abspath(os.getcwd()))

def _stub_engine(name: str):
    module = types.ModuleType(name)

    def run(path: str):  # noqa: ARG001
        return {"engine": name.split(".")[-2], "status": "ok", "detected": False, "verdict": "clean"}

    module.run = run
    return module


ENGINE_MODULES_TO_STUB = [
    "app.services.engines.clamav.engine",
]

for module_name in ENGINE_MODULES_TO_STUB:
    if module_name in sys.modules:
        continue

    try:
        __import__(module_name)
    except ImportError:
        sys.modules[module_name] = _stub_engine(module_name)

os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db_path}")
os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("STORAGE_PATH", _storage_dir)
os.environ.setdefault("ADMIN_DEFAULT_USERNAME", "admin")
os.environ.setdefault("ADMIN_DEFAULT_PASSWORD", "admin")
os.environ.setdefault("ADMIN_AUTH_SECRET", "test-secret")
os.environ.setdefault("ADMIN_AUTH_TTL_SECONDS", "3600")


@pytest.fixture(scope="session", autouse=True)
def infrastructure() -> Generator[None, None, None]:
    try:
        yield
    finally:
        shutil.rmtree(_storage_dir, ignore_errors=True)
        try:
            os.remove(_db_path)
        except OSError:
            pass


@pytest.fixture(autouse=True)
def reset_storage_service():
    from app.services import storage

    storage._storage_service = None
    yield
    storage._storage_service = None


@pytest.fixture(scope="session")
def celery_worker_instance():
    from app.workers.celery_app import celery

    celery.conf.task_always_eager = True
    celery.conf.task_eager_propagates = True
    celery.conf.broker_url = os.environ["CELERY_BROKER_URL"]
    celery.conf.result_backend = os.environ["CELERY_RESULT_BACKEND"]

    yield celery


@pytest.fixture(autouse=True)
def clean_database():
    from app.db.session import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    from app.main import app

    class SyncASGITransport(httpx.BaseTransport):
        def __init__(self, asgi_app):
            self._inner = httpx.ASGITransport(app=asgi_app)

        def handle_request(self, request: httpx.Request) -> httpx.Response:  # type: ignore[override]
            async def send() -> httpx.Response:
                response = await self._inner.handle_async_request(request)
                content = await response.aread()
                return httpx.Response(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=content,
                    extensions=response.extensions,
                    request=request,
                )

            return asyncio.run(send())

        def close(self) -> None:
            asyncio.run(self._inner.aclose())

    transport = SyncASGITransport(app)
    client = httpx.Client(transport=transport, base_url="http://testserver")
    try:
        yield client
    finally:
        client.close()


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: mark integration tests")
