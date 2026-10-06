import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-secret-change-me-before-deploying"

# Vercel runs the app as short-lived serverless functions: no disk that lasts, no
# long-running worker, and request bodies are capped at 4.5 MB. These defaults apply
# whenever Vercel's own VERCEL variable is present, and any setting can still override them.
VERCEL_DEFAULTS = {
    "environment": "production",
    "storage_backend": "database",
    "queue_backend": "inline",
    "sweep_enabled": False,
    "max_upload_mb": 4,
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"  # anything other than "dev" is treated as a real deployment
    database_url: str = "sqlite:///./dev.db"
    redis_url: str = "redis://localhost:6379/0"
    storage_backend: str = "local"  # "local" (disk) or "database" (inside Postgres)
    queue_backend: str = "redis"  # "redis" (separate worker) or "inline" (inside the upload request)
    storage_dir: str = "./storage"
    max_upload_mb: int = 200
    secret_key: str = DEV_SECRET
    token_minutes: int = 60
    sweep_enabled: bool = True
    sweep_every_seconds: int = 60
    stuck_after_minutes: int = 15
    cron_secret: str = ""  # lets Vercel Cron call the sweep endpoint. Empty means the endpoint is off.

    @model_validator(mode="before")
    @classmethod
    def apply_vercel_defaults(cls, values):
        if os.getenv("VERCEL"):
            for key, value in VERCEL_DEFAULTS.items():
                values.setdefault(key, value)
        return values

    @model_validator(mode="after")
    def tidy_and_check(self):
        # Hosts hand out "postgres://..." or "postgresql://...". SQLAlchemy needs the driver named.
        for prefix in ("postgres://", "postgresql://"):
            if self.database_url.startswith(prefix):
                self.database_url = "postgresql+psycopg://" + self.database_url[len(prefix):]
        if self.environment != "dev" and (self.secret_key == DEV_SECRET or len(self.secret_key) < 32):
            raise ValueError("Set SECRET_KEY to a random value of at least 32 characters when ENVIRONMENT is not 'dev'.")
        if self.storage_backend not in ("local", "database"):
            raise ValueError("STORAGE_BACKEND must be 'local' or 'database'.")
        if self.queue_backend not in ("redis", "inline"):
            raise ValueError("QUEUE_BACKEND must be 'redis' or 'inline'.")
        return self


settings = Settings()
