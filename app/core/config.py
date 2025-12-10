import os

class Settings:
    PROJECT_NAME: str = "GreenWeb Multi-AV"
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local").lower()
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "storage/files")
    STORAGE_S3_ENDPOINT: str | None = os.getenv("STORAGE_S3_ENDPOINT")
    STORAGE_S3_REGION: str | None = os.getenv("STORAGE_S3_REGION", "us-east-1")
    STORAGE_S3_BUCKET: str | None = os.getenv("STORAGE_S3_BUCKET")
    STORAGE_S3_ACCESS_KEY: str | None = os.getenv("STORAGE_S3_ACCESS_KEY")
    STORAGE_S3_SECRET_KEY: str | None = os.getenv("STORAGE_S3_SECRET_KEY")
    STORAGE_S3_USE_SSL: bool = os.getenv("STORAGE_S3_USE_SSL", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    STORAGE_TTL_SECONDS: int = int(os.getenv("STORAGE_TTL_SECONDS", "180"))
    STORAGE_MAX_BYTES: int = int(os.getenv("STORAGE_MAX_BYTES", str(5 * 1024 * 1024)))

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://multiav_user:mohammad@localhost:5432/multiav_db"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CLAMAV_SOCKET: str = os.getenv("CLAMAV_SOCKET", "/var/run/clamav/clamd.ctl")
    WINDEFENDER_HOST: str = os.getenv("WINDEFENDER_HOST", "windows-defender")
    WINDEFENDER_PORT: int = int(os.getenv("WINDEFENDER_PORT", "3993"))
    WINDEFENDER_TIMEOUT: int = int(os.getenv("WINDEFENDER_TIMEOUT", "120"))

settings = Settings()
