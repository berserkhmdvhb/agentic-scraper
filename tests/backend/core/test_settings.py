import logging
from pathlib import Path
from typing import Any, Callable
import pydantic

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
    MIN_LLM_SCHEMA_RETRIES,
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
    DEFAULT_LLM_SCHEMA_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_AGENT_MODE,
    DEFAULT_DUMP_LLM_JSON_DIR,
    DEFAULT_VERBOSE,
    DEFAULT_DEBUG_MODE,
)

def set_required_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AUTH0_DOMAIN", "test.auth0.com")
    monkeypatch.setenv("AUTH0_CLIENT_ID", "client-id")
    monkeypatch.setenv("AUTH0_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("API_AUDIENCE", "https://api.example.com")
    monkeypatch.setenv("ENCRYPTION_SECRET", "x" * 32)

# ---------- Core Settings Tests ----------

def test_settings_loads_correctly_from_env(settings: Settings) -> None:
    assert settings.project_name == PROJECT_NAME
    assert settings.env.value == DEFAULT_ENV
    assert settings.openai_model.value == DEFAULT_OPENAI_MODEL
    assert settings.log_level.value == DEFAULT_LOG_LEVEL
    assert settings.log_format.value == DEFAULT_LOG_FORMAT
    assert settings.agent_mode.value == DEFAULT_AGENT_MODE
    assert settings.debug_mode == DEFAULT_DEBUG_MODE
    assert settings.log_max_bytes == DEFAULT_LOG_MAX_BYTES
    assert settings.log_backup_count == DEFAULT_LOG_BACKUP_COUNT
    assert settings.log_dir == DEFAULT_LOG_DIR
    assert settings.screenshot_enabled == DEFAULT_SCREENSHOT_ENABLED
    assert settings.screenshot_dir == DEFAULT_SCREENSHOT_DIR
    assert settings.max_concurrent_requests == DEFAULT_MAX_CONCURRENT_REQUESTS
    assert settings.llm_max_tokens == DEFAULT_LLM_MAX_TOKENS
    assert settings.llm_temperature == DEFAULT_LLM_TEMPERATURE
    assert settings.request_timeout == DEFAULT_REQUEST_TIMEOUT
    assert settings.verbose == DEFAULT_VERBOSE
    assert settings.retry_attempts == DEFAULT_RETRY_ATTEMPTS
    assert settings.retry_backoff_min == DEFAULT_RETRY_BACKOFF_MIN
    assert settings.retry_backoff_max == DEFAULT_RETRY_BACKOFF_MAX
    assert settings.dump_llm_json_dir == DEFAULT_DUMP_LLM_JSON_DIR
    assert settings.llm_schema_retries == DEFAULT_LLM_SCHEMA_RETRIES


def test_settings_raises_on_missing_api_key(monkeypatch: MonkeyPatch, reset_settings_cache: Any) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)

    with pytest.raises(ValueError):
        Settings(
            auth0_domain="x",
            auth0_client_id="x",
            auth0_client_secret="x",
            api_audience="x",
            encryption_secret="x" * 32,
        )


def test_get_settings_is_cached(mock_env: None, reset_settings_cache: Any) -> None:
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


# ---------- Derived/Helper Method Tests ----------

def test_get_environment(mock_env: None, reset_settings_cache: Any) -> None:
    assert get_environment() == DEFAULT_ENV.upper()


def test_get_log_dir(mock_env: None, reset_settings_cache: Any) -> None:
    expected = Path(DEFAULT_LOG_DIR) / DEFAULT_ENV.upper()
    assert get_log_dir() == expected


def test_get_log_level_is_debug_in_verbose_mode(monkeypatch: MonkeyPatch, reset_settings_cache: Any) -> None:
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setenv("VERBOSE", "1")
    set_required_env(monkeypatch)

    assert get_log_level() == logging.DEBUG


def test_get_log_level_in_non_verbose_mode(monkeypatch: MonkeyPatch, reset_settings_cache: Any) -> None:
    monkeypatch.setenv("ENV", "PROD")
    monkeypatch.setenv("VERBOSE", "0")

    set_required_env(monkeypatch)


    expected_level = getattr(logging, DEFAULT_LOG_LEVEL.upper(), logging.INFO)
    assert get_log_level() == expected_level


def test_get_log_max_bytes(mock_env: None, reset_settings_cache: Any) -> None:
    assert get_log_max_bytes() == DEFAULT_LOG_MAX_BYTES


def test_get_log_backup_count(mock_env: None, reset_settings_cache: Any) -> None:
    assert get_log_backup_count() == DEFAULT_LOG_BACKUP_COUNT


def test_get_log_format(mock_env: None, reset_settings_cache: Any) -> None:
    assert get_log_format() == DEFAULT_LOG_FORMAT


# ---------- Derived Property Behavior ----------

def test_is_verbose_mode_true_if_env_dev(monkeypatch: MonkeyPatch, settings_factory: Any, reset_settings_cache: Any) -> None:
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setenv("VERBOSE", "0")
    set_required_env(monkeypatch)

    s = settings_factory()
    assert s.is_verbose_mode is True


def test_is_verbose_mode_true_if_verbose_true(monkeypatch: MonkeyPatch, settings_factory: Any, reset_settings_cache: Any) -> None:
    monkeypatch.setenv("ENV", "PROD")
    monkeypatch.setenv("VERBOSE", "1")
    set_required_env(monkeypatch)

    s = settings_factory()
    assert s.is_verbose_mode is True


def test_is_verbose_mode_false_by_default(monkeypatch: MonkeyPatch, settings_factory: Any, reset_settings_cache: Any) -> None:
    monkeypatch.setenv("ENV", "PROD")
    monkeypatch.setenv("VERBOSE", "0")
    set_required_env(monkeypatch)
    
    s = settings_factory()
    assert s.is_verbose_mode is False


# ---------- Field Exclusion Logic ----------

def test_excluded_fields_do_not_appear_in_model_dump(settings: Settings) -> None:
    dumped = settings.model_dump()
    assert "fetch_concurrency" not in dumped
    assert "llm_concurrency" not in dumped


# ---------- Bounds and Validation ----------

def test_llm_schema_retries_bounds(settings_factory: Callable[..., Settings]) -> None:
    # Must pass a real int (not a string) to trigger bounds validation
    with pytest.raises(pydantic.ValidationError) as exc_info:
        settings_factory(llm_schema_retries=-1)

    assert "llm_schema_retries" in str(exc_info.value)


def test_llm_temperature_out_of_bounds(settings_factory: Any) -> None:
    with pytest.raises(ValueError):
        settings_factory(llm_temperature=999)
