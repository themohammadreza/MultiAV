import os
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import admin_auth, admin_keys, health, results, scan, ui
from app.db.migrations import run_migrations
from app.services.orchestrator.registry import warm_up_active_engines
from app.services.storage import get_storage_service

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # starting the API
    from app.db import models
    from app.db.session import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    run_migrations(engine)

    storage = get_storage_service()
    if storage.backend == "s3":
        db = SessionLocal()
        try:
            storage.migrate_local_files(db)
        finally:
            db.close()

    warm_ups = warm_up_active_engines()
    if warm_ups:
        warmed = [name for name, ok in warm_ups.items() if ok]
        failed = [name for name, ok in warm_ups.items() if not ok]
        if warmed:
            logger.info("Warm-started engines: %s", ", ".join(sorted(warmed)))
        if failed:
            logger.warning("Engine warm-up failed: %s", ", ".join(sorted(failed)))
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

app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(scan.router, prefix="/api/v1/scan", tags=["Scan"])
app.include_router(results.router, prefix="/api/v1/results", tags=["Results"])
app.include_router(ui.router, prefix="/api/v1/ui", tags=["UI"])
app.include_router(admin_keys.router, prefix="/api/v1/admin/keys", tags=["Admin Keys"])
app.include_router(admin_auth.router, prefix="/api/v1/admin/auth", tags=["Admin Auth"])
