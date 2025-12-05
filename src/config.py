"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Network Monitor"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://netmon:netmon_secret@localhost:5432/network_monitor"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # NetBox
    netbox_url: str = "http://localhost:8000"
    netbox_token: str = ""

    # JWT Authentication
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Monitoring
    polling_interval_seconds: int = 30
    snmp_timeout_seconds: int = 5
    ssh_timeout_seconds: int = 30

    # Alerting
    webhook_url: str = ""
    webhook_timeout_seconds: int = 10

    # SNMP defaults
    snmp_community: str = "public"
    snmp_version: int = 2

    # SSH defaults (for pyATS/Genie routing polling)
    ssh_username: str = ""
    ssh_password: str = ""

    @property
    def sync_database_url(self) -> str:
        """Return synchronous database URL for Alembic migrations."""
        return self.database_url.replace("postgresql+asyncpg", "postgresql+psycopg2")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
