from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import results, scan, ui
from app.services.storage import get_storage_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # starting the API
    from app.db import models
    from app.db.session import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)

    storage = get_storage_service()
    if storage.backend == "s3":
        db = SessionLocal()
        try:
            storage.migrate_local_files(db)
        finally:
            db.close()
    yield


app = FastAPI(
    title = "GreenWeb Multi-AV",
    version = "0.1.0",
    lifespan = lifespan
)

app.include_router(scan.router, prefix="/api/v1/scan", tags=["Scan"])
app.include_router(results.router, prefix="/api/v1/results", tags=["Results"])
app.include_router(ui.router, prefix="/api/v1/ui", tags=["UI"])
