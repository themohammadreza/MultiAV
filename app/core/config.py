import os

class Settings:
    PROJECT_NAME: str = "GreenWeb Multi-AV"
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "storage/files")

settings = Settings()

