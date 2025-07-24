import logging
from pathlib import Path
from typing import Any

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
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_BACKOFF_MIN,
    DEFAULT_RETRY_BACKOFF_MAX,
    DEFAULT_SCREENSHOT_ENABLED,
    DEFAULT_SCREENSHOT_DIR,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_AGENT_MODE,
    DEFAULT_DUMP_LLM_JSON_DIR,
    DEFAULT_VERBOSE,
    DEFAULT_DEBUG_MODE,
)


# ---------- Core Settings Tests ----------

def test_settings_loads_correctly_from_env(
    mock_env: Any, reset_settings_cache: Any
) -> None:
    s = Settings()
    assert s.project_name == PROJECT_NAME
    assert s.env.value == DEFAULT_ENV
    assert s.openai_model.value == DEFAULT_OPENAI_MODEL
    assert s.log_level.value == DEFAULT_LOG_LEVEL
    assert s.log_format.value == DEFAULT_LOG_FORMAT
    assert s.agent_mode.value == DEFAULT_AGENT_MODE
    assert s.debug_mode == DEFAULT_DEBUG_MODE
    assert s.log_max_bytes == DEFAULT_LOG_MAX_BYTES
    assert s.log_backup_count == DEFAULT_LOG_BACKUP_COUNT
    assert s.log_dir == DEFAULT_LOG_DIR
    assert s.screenshot_enabled == DEFAULT_SCREENSHOT_ENABLED
    assert s.screenshot_dir == DEFAULT_SCREENSHOT_DIR
    assert s.max_concurrent_requests == DEFAULT_MAX_CONCURRENT_REQUESTS
    assert s.llm_max_tokens == DEFAULT_LLM_MAX_TOKENS
    assert s.llm_temperature == DEFAULT_LLM_TEMPERATURE
    assert s.request_timeout == DEFAULT_REQUEST_TIMEOUT
    assert s.verbose == DEFAULT_VERBOSE
    assert s.retry_attempts == DEFAULT_RETRY_ATTEMPTS
    assert s.retry_backoff_min == DEFAULT_RETRY_BACKOFF_MIN
    assert s.retry_backoff_max == DEFAULT_RETRY_BACKOFF_MAX
    assert s.dump_llm_json_dir == DEFAULT_DUMP_LLM_JSON_DIR


def test_settings_raises_on_missing_api_key(
    monkeypatch: MonkeyPatch, reset_settings_cache: Any
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)

    with pytest.raises(ValueError) as exc_info:
        Settings()
    assert "OPENAI_API_KEY" in str(exc_info.value)


def test_get_settings_is_cached(
    mock_env: Any, reset_settings_cache: Any
) -> None:
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


# ---------- Derived/Helper Method Tests ----------

def test_get_environment(
    mock_env: Any, reset_settings_cache: Any
) -> None:
    assert get_environment() == DEFAULT_ENV.upper()


def test_get_log_dir(
    mock_env: Any, reset_settings_cache: Any
) -> None:
    expected = Path(DEFAULT_LOG_DIR) / DEFAULT_ENV.upper()
    assert get_log_dir() == expected


def test_get_log_level_is_debug_in_verbose_mode(
    monkeypatch: MonkeyPatch, reset_settings_cache: Any
) -> None:
    monkeypatch.setenv("ENV", "DEV")  # or set VERBOSE=1
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    assert get_log_level() == logging.DEBUG


def test_get_log_level_in_non_verbose_mode(
    monkeypatch: MonkeyPatch, reset_settings_cache: Any
) -> None:
    monkeypatch.setenv("ENV", "PROD")
    monkeypatch.setenv("VERBOSE", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    expected_level = getattr(logging, DEFAULT_LOG_LEVEL.upper(), logging.INFO)
    assert get_log_level() == expected_level


def test_get_log_max_bytes(
    mock_env: Any, reset_settings_cache: Any
) -> None:
    assert get_log_max_bytes() == DEFAULT_LOG_MAX_BYTES


def test_get_log_backup_count(
    mock_env: Any, reset_settings_cache: Any
) -> None:
    assert get_log_backup_count() == DEFAULT_LOG_BACKUP_COUNT


def test_get_log_format(
    mock_env: Any, reset_settings_cache: Any
) -> None:
    assert get_log_format() == DEFAULT_LOG_FORMAT


# ---------- Derived Property Behavior ----------

def test_is_verbose_mode_true_if_env_dev(
    monkeypatch: MonkeyPatch, reset_settings_cache: Any
) -> None:
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    s = Settings()
    assert s.is_verbose_mode is True


def test_is_verbose_mode_true_if_verbose_true(
    monkeypatch: MonkeyPatch, reset_settings_cache: Any
) -> None:
    monkeypatch.setenv("VERBOSE", "1")
    monkeypatch.setenv("ENV", "PROD")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    s = Settings()
    assert s.is_verbose_mode is True


def test_is_verbose_mode_false_by_default(
    monkeypatch: MonkeyPatch, reset_settings_cache: Any
) -> None:
    monkeypatch.setenv("ENV", "PROD")
    monkeypatch.setenv("VERBOSE", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    s = Settings()
    assert s.is_verbose_mode is False


# ---------- Field Exclusion Logic ----------

def test_excluded_fields_do_not_appear_in_model_dump(
    mock_env: Any, reset_settings_cache: Any
) -> None:
    s = Settings()
    dumped = s.model_dump()
    assert "fetch_concurrency" not in dumped
    assert "llm_concurrency" not in dumped
