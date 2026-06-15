"""Application configuration.

All settings are loaded from environment variables (or a local ``.env`` file)
using ``pydantic-settings`` so the same image can be configured differently per
environment without code changes.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Application ---------------------------------------------------------
    environment: Literal["dev", "prod"] = "dev"
    debug: bool = True
    project_name: str = "Users API"
    api_v1_prefix: str = "/api/v1"

    # -- Database ------------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./users_api.db"

    # -- JWT -----------------------------------------------------------------
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # -- Verification --------------------------------------------------------
    verification_code_ttl_minutes: int = 60
    # Unverified accounts older than this are deleted by the cleanup task.
    unverified_account_ttl_hours: int = 48

    # -- Celery --------------------------------------------------------------
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # -- Bootstrap admin -----------------------------------------------------
    first_admin_email: str | None = Field(default=None)
    first_admin_password: str | None = Field(default=None)

    @property
    def is_dev(self) -> bool:
        return self.environment == "dev"


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance.

    ``lru_cache`` guarantees the environment is parsed only once per process,
    which also makes the settings object easy to override in tests.
    """
    return Settings()


settings = get_settings()
