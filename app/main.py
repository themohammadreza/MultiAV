from fastapi import FastAPI

from app.api.v1 import scan, results

def create_app() -> FastAPI:
    app = FastAPI(
        title="GreenWeb Multi-AV",
        version="0.1.0",
    )

    app.include_router(scan.router, prefix="/api/v1/scan", tags=["Scan"])
    app.include_router(results.router, prefix="/api/v1/results", tags=["Results"])

    return app

app = create_app()


