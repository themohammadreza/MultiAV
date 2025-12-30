import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.storage import get_storage_service


router = APIRouter()
logger = logging.getLogger(__name__)


def _check_database() -> tuple[bool, str | None]:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001 - readiness should tolerate missing deps
        logger.warning("Database readiness check failed: %s", exc)
        return False, str(exc)


def _check_storage() -> tuple[bool, str | None]:
    try:
        storage = get_storage_service()
        storage.check_ready()
        return True, None
    except Exception as exc:  # noqa: BLE001 - readiness should tolerate missing deps
        logger.warning("Storage readiness check failed: %s", exc)
        return False, str(exc)


@router.get("/health/")
def healthcheck() -> JSONResponse:
    """Readiness probe used by the UI and docker-compose healthchecks."""
    db_ok, db_error = _check_database()
    storage_ok, storage_error = _check_storage()

    checks = {
        "database": "ok" if db_ok else "error",
        "storage": "ok" if storage_ok else "error",
    }
    errors = {key: value for key, value in {"database": db_error, "storage": storage_error}.items() if value}

    if db_ok and storage_ok:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok", "checks": checks})

    payload = {"status": "error", "checks": checks, "errors": errors}
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)
