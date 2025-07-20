import logging
import os
from pathlib import Path
from pydantic import ValidationError
import pytest
from _pytest.monkeypatch import MonkeyPatch

from agentic_scraper.backend.core.settings import (
    Settings,
    get_settings,
    get_environment,
    get_log_dir,
    get_log_level,
    get_log_max_bytes,
    get_log_backup_count,
    get_log_format,
)
from agentic_scraper.backend.config.constants import (
    PROJECT_NAME,
    DEFAULT_ENV,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_MAX_BYTES,
    DEFAULT_LOG_BACKUP_COUNT,
    DEFAULT_LOG_DIR,
    DEFAULT_SCREENSHOT_ENABLED,
    DEFAULT_SCREENSHOT_DIR,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_REQUEST_TIMEOUT,
)


def test_settings_loads_correctly_from_env(
    mock_env: None, reset_settings_cache: None
) -> None:
    s = Settings() # type: ignore[call-arg]
    assert s.project_name == PROJECT_NAME
    assert s.env == DEFAULT_ENV
    assert s.debug_mode is True
    assert s.openai_model == DEFAULT_OPENAI_MODEL
    assert s.log_level == DEFAULT_LOG_LEVEL
    assert s.log_format == DEFAULT_LOG_FORMAT
    assert s.log_max_bytes == DEFAULT_LOG_MAX_BYTES
    assert s.log_backup_count == DEFAULT_LOG_BACKUP_COUNT
    assert s.log_dir == DEFAULT_LOG_DIR
    assert s.screenshot_enabled == DEFAULT_SCREENSHOT_ENABLED
    assert s.screenshot_dir == DEFAULT_SCREENSHOT_DIR
    assert s.max_concurrent_requests == DEFAULT_MAX_CONCURRENT_REQUESTS
    assert s.llm_max_tokens == DEFAULT_LLM_MAX_TOKENS
    assert s.llm_temperature == DEFAULT_LLM_TEMPERATURE
    assert s.request_timeout == DEFAULT_REQUEST_TIMEOUT


def test_settings_raises_on_missing_api_key(
    monkeypatch: MonkeyPatch, reset_settings_cache: None
) -> None:
    # Unset env var
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # Patch model config to disable .env loading
    monkeypatch.setitem(Settings.model_config, "env_file", None)

    assert "OPENAI_API_KEY" not in os.environ

    with pytest.raises(ValidationError) as exc_info:
        Settings()  # type: ignore[call-arg]

    assert "OPENAI_API_KEY" in str(exc_info.value)
    assert "Field required" in str(exc_info.value)

def test_get_settings_is_cached(
    mock_env: None, reset_settings_cache: None
) -> None:
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_get_environment(
    mock_env: None, reset_settings_cache: None
) -> None:
    assert get_environment() == DEFAULT_ENV.upper()


def test_get_log_dir(
    mock_env: None, reset_settings_cache: None
) -> None:
    expected = Path(DEFAULT_LOG_DIR) / DEFAULT_ENV.upper()
    assert get_log_dir() == expected


def test_get_log_level(
    mock_env: None, reset_settings_cache: None
) -> None:
    expected_level = getattr(logging, DEFAULT_LOG_LEVEL.upper(), logging.INFO)
    assert get_log_level() == expected_level


def test_get_log_max_bytes(
    mock_env: None, reset_settings_cache: None
) -> None:
    assert get_log_max_bytes() == DEFAULT_LOG_MAX_BYTES


def test_get_log_backup_count(
    mock_env: None, reset_settings_cache: None
) -> None:
    assert get_log_backup_count() == DEFAULT_LOG_BACKUP_COUNT


def test_get_log_format(
    mock_env: None, reset_settings_cache: None
) -> None:
    assert get_log_format() == DEFAULT_LOG_FORMAT
