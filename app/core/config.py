from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FreshBrain AI Engine"
    database_url: str
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5"
    stub_claude_api: bool = True
    warehouse_api_base_url: str = "http://localhost:8002"
    wms_base_url: str | None = None
    wms_api_key: str | None = None
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 15
    context_window_messages: int = 20
    summary_trigger_messages: int = 40
    worker_poll_interval_seconds: float = 5.0
    worker_lease_seconds: float = 300.0
    worker_max_attempts: int = 3
    dev_token_rate_limit: str = "5/minute"
    chat_rate_limit: str = "20/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
