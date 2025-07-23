import logging
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

from agentic_scraper.backend.config.aliases import (
    Environment,
    LogFormat,
    LogLevel,
    OpenAIModel,
)
from agentic_scraper.backend.config.constants import (
    DEFAULT_AGENT_MODE,
    DEFAULT_ENV,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_LOG_BACKUP_COUNT,
    DEFAULT_LOG_DIR,
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_MAX_BYTES,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SCREENSHOT_DIR,
    DEFAULT_SCREENSHOT_ENABLED,
    PROJECT_NAME,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_SETTINGS_LOADED,
    MSG_ERROR_MISSING_API_KEY,
)
from agentic_scraper.backend.core.settings_helpers import validated_settings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # General
    project_name: str = PROJECT_NAME
    debug_mode: bool = Field(default=False, validation_alias="DEBUG")
    env: Environment = Field(default=DEFAULT_ENV, validation_alias="ENV")

    # OpenAI
    openai_api_key: str = Field(..., validation_alias="OPENAI_API_KEY")
    openai_model: OpenAIModel = Field(default=DEFAULT_OPENAI_MODEL, validation_alias="OPENAI_MODEL")
    openai_project_id: str | None = Field(default=None, validation_alias="OPENAI_PROJECT_ID")

    # Network
    request_timeout: int = DEFAULT_REQUEST_TIMEOUT
    max_concurrent_requests: int = Field(
        default=DEFAULT_MAX_CONCURRENT_REQUESTS,
        validation_alias="MAX_CONCURRENT_REQUESTS",
        description="Max simultaneous fetches",
    )

    # Agent behavior
    llm_max_tokens: int = Field(default=DEFAULT_LLM_MAX_TOKENS, validation_alias="LLM_MAX_TOKENS")
    llm_temperature: float = Field(
        default=DEFAULT_LLM_TEMPERATURE, validation_alias="LLM_TEMPERATURE"
    )
    agent_mode: str = Field(
        default=DEFAULT_AGENT_MODE,
        validation_alias="AGENT_MODE",
        description="Which agent to use: fixed | adaptive | rule",
    )

    # Screenshotting
    screenshot_enabled: bool = Field(
        default=DEFAULT_SCREENSHOT_ENABLED, validation_alias="SCREENSHOT_ENABLED"
    )
    screenshot_dir: str = Field(default=DEFAULT_SCREENSHOT_DIR, validation_alias="SCREENSHOT_DIR")

    # Logging
    log_dir: str = Field(default=DEFAULT_LOG_DIR, validation_alias="LOG_DIR")
    log_level: LogLevel = Field(default=DEFAULT_LOG_LEVEL, validation_alias="LOG_LEVEL")
    log_max_bytes: int = Field(default=DEFAULT_LOG_MAX_BYTES, validation_alias="LOG_MAX_BYTES")
    log_backup_count: int = Field(
        default=DEFAULT_LOG_BACKUP_COUNT, validation_alias="LOG_BACKUP_COUNT"
    )
    log_format: LogFormat = Field(default=DEFAULT_LOG_FORMAT, validation_alias="LOG_FORMAT")

    # Execution tuning (CLI/batch mode only)
    fetch_concurrency: int = Field(default=10, validation_alias="FETCH_CONCURRENCY", exclude=True)
    llm_concurrency: int = Field(default=2, validation_alias="LLM_CONCURRENCY", exclude=True)

    # Retry behavior (used in agent.py with tenacity)
    retry_attempts: int = Field(
        default=2,
        validation_alias="RETRY_ATTEMPTS",
        description="Number of times to retry transient LLM errors (OpenAIError)",
    )
    retry_backoff_min: float = Field(
        default=1.0,
        validation_alias="RETRY_BACKOFF_MIN",
        description="Minimum backoff time (seconds) for retry delay",
    )
    retry_backoff_max: float = Field(
        default=10.0,
        validation_alias="RETRY_BACKOFF_MAX",
        description="Maximum backoff time (seconds) for retry delay",
    )

    @model_validator(mode="before")
    @classmethod
    def apply_validations(cls, values: dict[str, Any]) -> dict[str, Any]:
        return validated_settings(values)

    @model_validator(mode="after")
    def validate_config(self) -> "Settings":
        safe_dump = self.model_dump(exclude={"openai_api_key", "openai_project_id"})
        logger.debug(MSG_DEBUG_SETTINGS_LOADED.format(safe_dump=safe_dump))

        if not self.openai_api_key:
            raise ValueError(MSG_ERROR_MISSING_API_KEY)
        return self

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def get_environment() -> str:
    return get_settings().env.upper()


def get_log_dir() -> Path:
    return Path(get_settings().log_dir) / get_environment()


def get_log_level() -> int:
    level_str = get_settings().log_level.upper()
    return getattr(logging, level_str, logging.INFO)


def get_log_max_bytes() -> int:
    return get_settings().log_max_bytes


def get_log_backup_count() -> int:
    return get_settings().log_backup_count


def get_log_format() -> str:
    return get_settings().log_format
