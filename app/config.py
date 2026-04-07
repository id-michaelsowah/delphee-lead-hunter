from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # AI API Keys
    gemini_api_key: str
    anthropic_api_key: str

    # Database backend: "sql" or "firestore"
    db_backend: str = "sql"

    # SQL backend (SQLite for dev, PostgreSQL for production)
    database_url: str = "sqlite+aiosqlite:///./delphee.db"

    # Firestore backend (Cloud Run)
    google_cloud_project: Optional[str] = None

    # Email notifications (optional)
    sendgrid_api_key: Optional[str] = None
    alert_email: Optional[str] = None

    # App
    secret_key: str = "dev-secret-change-me"
    port: int = 8000
    app_password: Optional[str] = None

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
