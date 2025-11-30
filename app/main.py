from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.api.v1 import scan, results

@asynccontextmanager
async def lifespan(app: FastAPI):
    # starting the API
    from app.db.session import Base, engine
    from app.db import models

    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title = "GreenWeb Multi-AV",
    version = "0.1.0",
    lifespan = lifespan
)

app.include_router(scan.router, prefix="/api/v1/scan", tags=["Scan"])
app.include_router(results.router, prefix="/api/v1/results", tags=["Results"])
