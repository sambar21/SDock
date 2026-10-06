from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-secret-change-me-before-deploying"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"  # anything other than "dev" is treated as a real deployment
    database_url: str = "sqlite:///./dev.db"
    redis_url: str = "redis://localhost:6379/0"
    storage_dir: str = "./storage"
    max_upload_mb: int = 200
    secret_key: str = DEV_SECRET
    token_minutes: int = 60
    sweep_enabled: bool = True
    sweep_every_seconds: int = 60
    stuck_after_minutes: int = 15

    @model_validator(mode="after")
    def refuse_weak_secret_outside_dev(self):
        if self.environment != "dev" and (self.secret_key == DEV_SECRET or len(self.secret_key) < 32):
            raise ValueError("Set SECRET_KEY to a random value of at least 32 characters when ENVIRONMENT is not 'dev'.")
        return self


settings = Settings()
