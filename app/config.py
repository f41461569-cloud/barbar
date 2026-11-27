import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./barbar_smart.db"
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    ALGORITHM: str = "HS256"
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    # Deployment-level code for admin registration/login (ADR 007). Empty means
    # admin endpoints are disabled; there is deliberately no default secret.
    ADMIN_CODE: str = os.getenv("ADMIN_CODE", "")

settings = Settings()
