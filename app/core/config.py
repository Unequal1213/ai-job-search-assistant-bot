"""Typed runtime configuration loaded from environment variables."""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.limits import WorkflowLimits


class Environment(StrEnum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application settings with conservative validated limits."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    bot_token: SecretStr | None = None
    database_url: SecretStr
    log_level: str = "INFO"
    environment: Environment = Environment.DEVELOPMENT
    deterministic_provider_version: str = Field(
        default="rules-v1", min_length=1, max_length=64
    )

    max_vacancy_text_chars: int = Field(default=12_000, ge=100, le=50_000)
    max_cover_letter_context_chars: int = Field(default=8_000, ge=100, le=50_000)
    max_message_chars: int = Field(default=12_000, ge=100, le=50_000)
    max_active_workflows_per_actor: int = Field(default=1, ge=1, le=10)
    workflow_timeout_seconds: int = Field(default=120, ge=5, le=3_600)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=86_400)
    rate_limit_requests_per_window: int = Field(default=5, ge=1, le=1_000)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Accept standard logging levels without exposing other settings."""
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("log_level must be a standard Python logging level")
        return normalized

    @property
    def workflow_limits(self) -> WorkflowLimits:
        """Return immutable domain limits for workflow services."""
        return WorkflowLimits(
            max_vacancy_text_chars=self.max_vacancy_text_chars,
            max_cover_letter_context_chars=self.max_cover_letter_context_chars,
            max_message_chars=self.max_message_chars,
            max_active_workflows_per_actor=self.max_active_workflows_per_actor,
            workflow_timeout_seconds=self.workflow_timeout_seconds,
            rate_limit_window_seconds=self.rate_limit_window_seconds,
            rate_limit_requests_per_window=self.rate_limit_requests_per_window,
        )


@lru_cache
def get_settings() -> Settings:
    """Load cached runtime settings from environment and optional local .env."""
    return Settings()  # type: ignore[call-arg]
