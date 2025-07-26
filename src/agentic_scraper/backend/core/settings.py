import logging
from functools import cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

from agentic_scraper.backend.config.constants import (
    DEFAULT_AUTH0_ALGORITHM,
    DEFAULT_DEBUG_MODE,
    DEFAULT_DUMP_LLM_JSON_DIR,
    DEFAULT_FETCH_CONCURRENCY,
    DEFAULT_LLM_CONCURRENCY,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_SCHEMA_RETRIES,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_LOG_BACKUP_COUNT,
    DEFAULT_LOG_DIR,
    DEFAULT_LOG_MAX_BYTES,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_BACKOFF_MAX,
    DEFAULT_RETRY_BACKOFF_MIN,
    DEFAULT_SCREENSHOT_DIR,
    DEFAULT_SCREENSHOT_ENABLED,
    DEFAULT_VERBOSE,
    MAX_FETCH_CONCURRENCY,
    MAX_LLM_CONCURRENCY,
    MAX_LLM_MAX_TOKENS,
    MAX_LLM_SCHEMA_RETRIES,
    MAX_LLM_TEMPERATURE,
    MAX_RETRY_ATTEMPTS,
    MIN_BACKOFF_SECONDS,
    MIN_FETCH_CONCURRENCY,
    MIN_LLM_CONCURRENCY,
    MIN_LLM_MAX_TOKENS,
    MIN_LLM_SCHEMA_RETRIES,
    MIN_LLM_TEMPERATURE,
    MIN_MAX_CONCURRENT_REQUESTS,
    MIN_RETRY_ATTEMPTS,
    PROJECT_NAME,
    VALID_AGENT_MODES,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_SETTINGS_LOADED_WITH_VALUES,
)
from agentic_scraper.backend.config.types import (
    AgentMode,
    Environment,
    LogFormat,
    LogLevel,
    OpenAIModel,
)
from agentic_scraper.backend.core.settings_helpers import validated_settings
from agentic_scraper.backend.scraper.models import OpenAIConfig
from agentic_scraper.backend.utils.validators import (
    validate_backoff_range,
    validate_log_rotation_config,
    validate_openai_api_key,
)

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # General
    project_name: str = PROJECT_NAME
    debug_mode: bool = Field(default=DEFAULT_DEBUG_MODE, validation_alias="DEBUG")
    env: Environment = Field(default=Environment.DEV, validation_alias="ENV")

    # OpenAI
    openai_model: OpenAIModel = Field(default=OpenAIModel.GPT_3_5, validation_alias="OPENAI_MODEL")
    openai: OpenAIConfig  # Now the OpenAIConfig model is nested under 'openai'

    # Network
    request_timeout: int = DEFAULT_REQUEST_TIMEOUT
    max_concurrent_requests: int = Field(
        default=DEFAULT_MAX_CONCURRENT_REQUESTS,
        validation_alias="MAX_CONCURRENT_REQUESTS",
        ge=MIN_MAX_CONCURRENT_REQUESTS,
        description="Max simultaneous fetches",
    )

    # Agent behavior

    agent_mode: AgentMode = Field(
        default=AgentMode.LLM_FIXED,
        validation_alias="AGENT_MODE",
        description=f"Which agent to use: {', '.join(sorted(VALID_AGENT_MODES))}",
    )
    llm_max_tokens: int = Field(
        default=DEFAULT_LLM_MAX_TOKENS,
        validation_alias="LLM_MAX_TOKENS",
        ge=MIN_LLM_MAX_TOKENS,
        le=MAX_LLM_MAX_TOKENS,
    )
    llm_temperature: float = Field(
        default=DEFAULT_LLM_TEMPERATURE,
        validation_alias="LLM_TEMPERATURE",
        ge=MIN_LLM_TEMPERATURE,
        le=MAX_LLM_TEMPERATURE,
    )

    # Screenshotting
    screenshot_enabled: bool = Field(
        default=DEFAULT_SCREENSHOT_ENABLED, validation_alias="SCREENSHOT_ENABLED"
    )
    screenshot_dir: str = Field(default=DEFAULT_SCREENSHOT_DIR, validation_alias="SCREENSHOT_DIR")

    # Logging
    log_dir: str = Field(default=DEFAULT_LOG_DIR, validation_alias="LOG_DIR")
    log_level: LogLevel = Field(default=LogLevel.INFO, validation_alias="LOG_LEVEL")
    log_max_bytes: int = Field(default=DEFAULT_LOG_MAX_BYTES, validation_alias="LOG_MAX_BYTES")
    log_backup_count: int = Field(
        default=DEFAULT_LOG_BACKUP_COUNT, validation_alias="LOG_BACKUP_COUNT"
    )
    log_format: LogFormat = Field(default=LogFormat.PLAIN, validation_alias="LOG_FORMAT")
    verbose: bool = Field(
        default=DEFAULT_VERBOSE,
        validation_alias="VERBOSE",
        description="If true, enables detailed debug logs and full tracebacks.",
    )

    # Execution tuning (CLI/batch mode only)
    fetch_concurrency: int = Field(
        default=DEFAULT_FETCH_CONCURRENCY,
        validation_alias="FETCH_CONCURRENCY",
        exclude=True,
        ge=MIN_FETCH_CONCURRENCY,
        le=MAX_FETCH_CONCURRENCY,
    )

    llm_concurrency: int = Field(
        default=DEFAULT_LLM_CONCURRENCY,
        validation_alias="LLM_CONCURRENCY",
        exclude=True,
        ge=MIN_LLM_CONCURRENCY,
        le=MAX_LLM_CONCURRENCY,
    )

    # Retry behavior (used in agent.py with tenacity)
    dump_llm_json_dir: str | None = Field(
        default=DEFAULT_DUMP_LLM_JSON_DIR,
        validation_alias="DUMP_LLM_JSON_DIR",
        description="Optional directory to dump full LLM parsed data for debugging/inspection.",
    )
    retry_attempts: int = Field(
        default=DEFAULT_RETRY_ATTEMPTS,
        validation_alias="RETRY_ATTEMPTS",
        ge=MIN_RETRY_ATTEMPTS,
        le=MAX_RETRY_ATTEMPTS,
        description="Number of times to retry transient LLM errors (OpenAIError)",
    )
    retry_backoff_min: float = Field(
        default=DEFAULT_RETRY_BACKOFF_MIN,
        validation_alias="RETRY_BACKOFF_MIN",
        ge=MIN_BACKOFF_SECONDS,
        description="Minimum backoff time (seconds) for retry delay",
    )
    retry_backoff_max: float = Field(
        default=DEFAULT_RETRY_BACKOFF_MAX,
        validation_alias="RETRY_BACKOFF_MAX",
        ge=MIN_BACKOFF_SECONDS,
        description="Maximum backoff time (seconds) for retry delay",
    )

    llm_schema_retries: Annotated[
        int,
        Field(
            validation_alias="LLM_SCHEMA_RETRIES",
            ge=MIN_LLM_SCHEMA_RETRIES,
            le=MAX_LLM_SCHEMA_RETRIES,
            description="How many times to retry adaptive LLM prompts "
            "if required fields are missing.",
        ),
    ] = DEFAULT_LLM_SCHEMA_RETRIES

    # Authentication & Security
    auth0_domain: str = Field(..., validation_alias="AUTH0_DOMAIN")
    auth0_client_id: str = Field(..., validation_alias="AUTH0_CLIENT_ID")
    auth0_client_secret: str = Field(..., validation_alias="AUTH0_CLIENT_SECRET")
    api_audience: str = Field(..., validation_alias="API_AUDIENCE")
    auth0_algorithms: list[str] = Field(default=[DEFAULT_AUTH0_ALGORITHM])
    encryption_secret: str = Field(..., validation_alias="ENCRYPTION_SECRET")

    # Derived
    @property
    def is_verbose_mode(self) -> bool:
        return self.env.upper() == "DEV" or self.verbose

    @model_validator(mode="before")
    @classmethod
    def apply_validations(cls, values: dict[str, Any]) -> dict[str, Any]:
        return validated_settings(values)

    @model_validator(mode="after")
    def validate_config(self) -> "Settings":
        # Validate OpenAI API key
        validate_openai_api_key(self.openai.api_key)  # Access through `self.openai.api_key`

        # Validate retry backoff range
        validate_backoff_range(self.retry_backoff_min, self.retry_backoff_max)
        validate_log_rotation_config(self.log_max_bytes, self.log_backup_count)
        return self

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "validate_default": True,
        "validate_assignment": True,
    }


@cache
def get_settings() -> Settings:
    return Settings.model_validate({})


def log_settings(settings: Settings) -> None:
    if getattr(log_settings, "already_logged", False):
        return
    log_settings.already_logged = True  # type: ignore[attr-defined]

    safe_dump = settings.model_dump(
        exclude={"openai"},  # Exclude the entire 'openai' attribute
        mode="json",
    )
    formatted = "\n".join(f"  {k}: {v}" for k, v in safe_dump.items())
    logger.info(MSG_DEBUG_SETTINGS_LOADED_WITH_VALUES.format(values=formatted))


def get_environment() -> str:
    return get_settings().env.upper()


def get_log_dir() -> Path:
    return Path(get_settings().log_dir) / get_environment()


def get_log_level() -> int:
    settings = get_settings()
    if settings.is_verbose_mode:
        return logging.DEBUG
    level_str = settings.log_level.upper()
    return getattr(logging, level_str, logging.INFO)


def get_log_max_bytes() -> int:
    return get_settings().log_max_bytes


def get_log_backup_count() -> int:
    return get_settings().log_backup_count


def get_log_format() -> str:
    return get_settings().log_format
