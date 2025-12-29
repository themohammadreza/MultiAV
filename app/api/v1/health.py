from fastapi import APIRouter


router = APIRouter()


@router.get("/health/")
def healthcheck():
    """Lightweight readiness probe used by the UI to wait for startup completion."""
    return {"status": "ok"}
