"""
Central runtime configuration for the Agentic Scraper backend.

Responsibilities:
- Define and validate application settings (env-driven) using `pydantic-settings`.
- Provide a cached accessor `get_settings()` for process-wide configuration.
- Expose helpers for logging configuration (dir, level, rotation).
- Emit a one-time sanitized dump of effective settings for observability.

Public API:
- `Settings`: Pydantic settings model (validated from environment).
- `get_settings()`: Cached process-local instance of `Settings`.
- `log_settings(settings)`: One-time info log of effective (non-sensitive) settings.
- `get_environment()`: Uppercased environment string (e.g., 'DEV', 'PROD').
- `get_log_dir()`: Effective log directory (including environment suffix).
- `get_log_level()`: Integer log level honoring verbose mode.
- `get_log_max_bytes()`, `get_log_backup_count()`, `get_log_format()`: Logging knobs.

Config:
- Reads from environment variables (see individual `Field(validation_alias=...)`).
- `.env` file is supported (`env_file=".env", env_file_encoding="utf-8"`).

Operational:
- Concurrency: `get_settings()` is cached per-process via `functools.cache`.
- Validation: Cross-field normalization via `validated_settings` (mode="before"),
  plus field-level and (mode="after") invariants.
- Logging: Sensitive values (e.g., `openai`) are excluded from logs.

Usage:
    from agentic_scraper.backend.core.settings import get_settings, log_settings
    settings = get_settings()
    log_settings(settings)  # logs once per process

Notes:
- Do not mutate the returned `Settings` instance globally; prefer overrides via
  Pydantic's `.model_copy(update=...)` in request-scoped flows.
- Environment names are modeled by `Environment` enum; `is_verbose_mode` treats
  DEV or explicit `VERBOSE=true` as verbose.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

from agentic_scraper.backend.config.constants import (
    DEFAULT_AGENT_MODE,
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
from agentic_scraper.backend.config.messages import MSG_DEBUG_SETTINGS_LOADED_WITH_VALUES
from agentic_scraper.backend.config.types import (
    AgentMode,
    Environment,
    LogFormat,
    LogLevel,
    OpenAIConfig,
    OpenAIModel,
)
from agentic_scraper.backend.core.settings_helpers import validated_settings
from agentic_scraper.backend.utils.validators import (
    validate_backoff_range,
    validate_log_rotation_config,
    validate_openai_api_key,
)

logger = logging.getLogger(__name__)

__all__ = [
    "Settings",
    "get_environment",
    "get_log_backup_count",
    "get_log_dir",
    "get_log_format",
    "get_log_level",
    "get_log_max_bytes",
    "get_settings",
    "log_settings",
]


@dataclass
class _Once:
    """Sentinel to ensure a single execution (e.g., one-time settings log)."""

    done: bool = False


_LOG_SETTINGS_ONCE = _Once()  # module-level sentinel


class Settings(BaseSettings):
    """
    Central process/runtime configuration.

    Environment variables are validated/coerced in two stages:
      1) `validated_settings` runs (mode="before") for cross-field/coercion logic.
      2) Pydantic field validators + the (mode="after") validator enforce invariants.

    Attributes:
        project_name (str): Human-readable project name.
        debug_mode (bool): Light-weight debug feature flag (distinct from `verbose`).
        env (Environment): Execution environment enum.
        openai_model (OpenAIModel): Default model for LLM agents.
        openai (OpenAIConfig | None): Optional default OpenAI credentials.
        request_timeout (int): Per-request HTTP timeout (seconds).
        max_concurrent_requests (int): Max simultaneous fetches.
        agent_mode (AgentMode): Default agent mode (e.g., 'llm_fixed', 'rule_based').
        llm_max_tokens (int): Default token ceiling for LLM calls.
        llm_temperature (float): Default sampling temperature for LLM calls.
        screenshot_enabled (bool): Enable screenshot capture.
        screenshot_dir (str): Directory for screenshots.
        log_dir (str): Base log directory.
        log_level (LogLevel): Minimum log level.
        log_max_bytes (int): Rotation size for log files.
        log_backup_count (int): Number of rotated files to keep.
        log_format (LogFormat): Plain vs JSON log format.
        verbose (bool): Extra debug logs and full tracebacks.
        fetch_concurrency (int): Fetch worker concurrency (CLI/batch paths).
        llm_concurrency (int): LLM call concurrency (CLI/batch paths).
        dump_llm_json_dir (str | None): Optional path to dump parsed LLM JSON.
        retry_attempts (int): Retry attempts for transient LLM errors.
        retry_backoff_min (float): Minimum retry backoff (seconds).
        retry_backoff_max (float): Maximum retry backoff (seconds).
        llm_schema_retries (int): Retries for schema validation of LLM outputs.
        auth0_* (str/list[str]): Auth0 configuration (issuer, domain, client, algorithms).
        encryption_secret (str): Secret used for local encryption.
        backend_domain (str): Public backend base URL (used in OpenAPI servers).
        auth0_api_audience (str): API audience for Auth0.
        frontend_domain (str): Frontend domain used for redirects/CORS.
        auth0_redirect_uri (str): Redirect URI for OAuth flows.

    Properties:
        is_verbose_mode (bool): True if `env=DEV` or `verbose=True`.

    Notes:
        - Some fields are marked `exclude=True` to keep them out of settings dumps.
        - Use `.model_copy(update=...)` for request-scoped overrides (no globals).
    """

    # General
    project_name: str = PROJECT_NAME
    debug_mode: bool = Field(default=DEFAULT_DEBUG_MODE, validation_alias="DEBUG")
    env: Environment = Field(default=Environment.DEV, validation_alias="ENV")

    # OpenAI
    openai_model: OpenAIModel = Field(default=OpenAIModel.GPT_3_5, validation_alias="OPENAI_MODEL")
    openai: OpenAIConfig | None = None

    # Network
    request_timeout: int = Field(
        default=DEFAULT_REQUEST_TIMEOUT,
        ge=1,  # complement to validator; ensures positive integer at the field level
        description="Per-request timeout in seconds for HTTP calls.",
    )
    max_concurrent_requests: int = Field(
        default=DEFAULT_MAX_CONCURRENT_REQUESTS,
        validation_alias="MAX_CONCURRENT_REQUESTS",
        ge=MIN_MAX_CONCURRENT_REQUESTS,
        description="Max simultaneous fetches",
    )

    # Agent behavior
    agent_mode: AgentMode = Field(
        default=DEFAULT_AGENT_MODE,
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
        exclude=True,  # exclude from dumps to keep API output smaller
        ge=MIN_FETCH_CONCURRENCY,
        le=MAX_FETCH_CONCURRENCY,
    )

    llm_concurrency: int = Field(
        default=DEFAULT_LLM_CONCURRENCY,
        validation_alias="LLM_CONCURRENCY",
        exclude=True,  # exclude from dumps to keep API output smaller
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
    auth0_issuer: str = Field(..., validation_alias="AUTH0_ISSUER")
    auth0_client_id: str = Field(..., validation_alias="AUTH0_CLIENT_ID")
    auth0_client_secret: str = Field(..., validation_alias="AUTH0_CLIENT_SECRET")

    auth0_algorithms: list[str] = Field(
        default=[DEFAULT_AUTH0_ALGORITHM],
        validation_alias="AUTH0_ALGORITHMS",
    )
    encryption_secret: str = Field(..., validation_alias="ENCRYPTION_SECRET")

    # Frontend & Backend Domains
    backend_domain: str = Field(..., validation_alias="BACKEND_DOMAIN")
    auth0_api_audience: str = Field(..., validation_alias="AUTH0_API_AUDIENCE")
    frontend_domain: str = Field(..., validation_alias="FRONTEND_DOMAIN")
    auth0_redirect_uri: str = Field(..., validation_alias="AUTH0_REDIRECT_URI")

    # Derived helpers
    @property
    def is_verbose_mode(self) -> bool:
        """
        True if running in DEV or if the explicit verbose flag is set.

        Returns:
            bool: Whether verbose/debug-level logging should be enabled.
        """
        env_obj = self.env
        env_upper = (env_obj.value if hasattr(env_obj, "value") else str(env_obj)).upper()
        return env_upper == "DEV" or self.verbose

    @model_validator(mode="before")
    @classmethod
    def apply_validations(cls, values: dict[str, Any]) -> dict[str, Any]:
        """
        Apply cross-field coercions and normalization before field parsing.

        Args:
            values (dict[str, Any]): Raw environment values.

        Returns:
            dict[str, Any]: Normalized values passed to Pydantic parsing.
        """
        # Coerce + validate raw values (strings/env) before field parsing.
        return validated_settings(values)

    @model_validator(mode="after")
    def validate_config(self) -> Settings:
        """
        Enforce invariants after all fields are parsed.

        Validates:
            - Provided OpenAI API key shape (if present).
            - Backoff range (min <= max).
            - Log rotation configuration (size/count).

        Returns:
            Settings: The validated instance.
        """
        # Validate OpenAI API key if provided
        if self.openai:
            validate_openai_api_key(self.openai.api_key)

        # Validate retry & log-rotation ranges
        validate_backoff_range(self.retry_backoff_min, self.retry_backoff_max)
        validate_log_rotation_config(self.log_max_bytes, self.log_backup_count)
        return self

    # Pydantic model configuration
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "validate_default": True,
        "validate_assignment": True,
    }


@cache
def get_settings() -> Settings:
    """
    Load and cache settings once per process.

    Returns:
        Settings: The process-wide configuration object.

    Notes:
        - Cached via `functools.cache` to avoid repeated env parsing.
        - Use `.model_copy(update=...)` for request-scoped overrides.
    """
    return Settings.model_validate({})


def log_settings(settings: Settings) -> None:
    """
    Log current settings only once per process lifetime.

    Sensitive values (like `openai`) are excluded.

    Args:
        settings (Settings): The settings instance to log.

    Returns:
        None
    """
    if _LOG_SETTINGS_ONCE.done:
        return
    _LOG_SETTINGS_ONCE.done = True

    # Exclude sensitive fields; ensure JSON-safe dump.
    safe_dump = settings.model_dump(
        exclude={"openai"},
        mode="json",
    )
    formatted = "\n".join(f"  {k}: {v}" for k, v in safe_dump.items())
    logger.info(MSG_DEBUG_SETTINGS_LOADED_WITH_VALUES.format(values=formatted))


def get_environment() -> str:
    """
    Return the uppercased environment value (e.g., 'DEV', 'PROD').

    Returns:
        str: Uppercased env name from settings.
    """
    env_obj = get_settings().env
    return (env_obj.value if hasattr(env_obj, "value") else str(env_obj)).upper()


def get_log_dir() -> Path:
    """
    Compute the effective log directory including environment suffix.

    Returns:
        Path: Path to the directory where logs should be written.
    """
    return Path(get_settings().log_dir) / get_environment()


def get_log_level() -> int:
    """
    Resolve the effective logging level integer for the runtime.

    Honors verbose mode by forcing DEBUG.

    Returns:
        int: An integer constant from the `logging` module (e.g., logging.INFO).
    """
    settings = get_settings()
    if settings.is_verbose_mode:
        return logging.DEBUG

    # Support enum or plain string values
    lvl = settings.log_level
    level_str = lvl.value if hasattr(lvl, "value") else str(lvl)
    level_str = level_str.upper()
    return getattr(logging, level_str, logging.INFO)


def get_log_max_bytes() -> int:
    """
    Return the max log file size (bytes) before rotation.

    Returns:
        int: Maximum size in bytes.
    """
    return get_settings().log_max_bytes


def get_log_backup_count() -> int:
    """
    Return the number of rotated log files to retain.

    Returns:
        int: Backup file count.
    """
    return get_settings().log_backup_count


def get_log_format() -> str:
    """
    Return the configured log format ('plain' or 'json').

    Returns:
        str: Log format name.
    """
    fmt = get_settings().log_format
    return fmt.value if hasattr(fmt, "value") else str(fmt)
