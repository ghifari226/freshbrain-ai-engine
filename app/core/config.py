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
    # Self-issued for now (see app/dev/router.py) — no default on purpose,
    # the app should fail to start rather than sign tokens with a guessable
    # secret. Once chat-gateway mints real tokens (v0.5.0 Beta), this either
    # becomes a shared secret with gateway or gets replaced by an RS256
    # public key — not decided yet, see freshbrain-agreement/VERSIONING.md.
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 15
    # Rolling conversation summarization: X = messages always sent raw to
    # Claude, N = total messages before summarization ever kicks in.
    context_window_messages: int = 20
    summary_trigger_messages: int = 40
    worker_poll_interval_seconds: float = 5.0
    # A crashed worker leaves a job stuck in "processing" forever without
    # this — claim_next() reclaims anything stuck past the lease as
    # "pending" (or "failed" once it's already used up its attempts).
    worker_lease_seconds: float = 300.0
    worker_max_attempts: int = 3
    # Rate limiting only for now — no cache/locks/queue on Redis yet, not a
    # rule against it, just not needed until something actually calls for it.
    rate_limit_storage_uri: str = "redis://localhost:6379/0"
    dev_token_rate_limit: str = "5/minute"
    chat_rate_limit: str = "20/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
