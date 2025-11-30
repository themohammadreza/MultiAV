import os

class Settings:
    PROJECT_NAME: str = "GreenWeb Multi-AV"
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "storage/files")

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://multiav_user:mohammad@localhost:5432/multiav_db"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CLAMAV_SOCKET: str = os.getenv("CLAMAV_SOCKET", "/var/run/clamav/clamd.ctl")

settings = Settings()
