import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# Allow browser apps (e.g., the Next.js UI) to call the API without CORS failures.
cors_origins = os.getenv("CORS_ORIGINS")
allowed_origins = (
    [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
    if cors_origins
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.include_router(scan.router, prefix="/api/v1/scan", tags=["Scan"])
app.include_router(results.router, prefix="/api/v1/results", tags=["Results"])
app.include_router(ui.router, prefix="/api/v1/ui", tags=["UI"])
