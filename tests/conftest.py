"""
Global pytest fixtures for agentic_scraper test suite.

This file provides reusable fixtures to:
- Clear environment variables
- Control `.env` and setting overrides
- Reset cached `get_settings()`
- Capture logging output for assertions
"""

import importlib
import logging
from collections.abc import Generator
from io import StringIO
from pathlib import Path
from typing import Callable, ContextManager

import pytest
from _pytest.monkeypatch import MonkeyPatch
from unittest.mock import patch

from agentic_scraper.backend.core import settings as settings_module
from agentic_scraper.backend.config.constants import (
    DEFAULT_AGENT_MODE,
    DEFAULT_ENV,
    DEFAULT_DUMP_LLM_JSON_DIR,
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
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_BACKOFF_MIN,
    DEFAULT_RETRY_BACKOFF_MAX,
    DEFAULT_VERBOSE,
    DEFAULT_DEBUG_MODE,
)

__all__ = [
    "clear_agentic_env",
    "reset_settings_cache",
    "reload_settings",
    "set_env_var",
    "log_stream",
    "debug_logger",
]

# ---------------------------------------------------------------------
# Environment Cleanup and Settings Reset
# ---------------------------------------------------------------------


@pytest.fixture
def mock_env(monkeypatch: MonkeyPatch) -> Generator[None, None, None]:
    """Set up environment variables with valid defaults for Settings."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ENV", DEFAULT_ENV)
    monkeypatch.setenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    monkeypatch.setenv("LOG_LEVEL", DEFAULT_LOG_LEVEL)
    monkeypatch.setenv("LOG_FORMAT", DEFAULT_LOG_FORMAT)
    monkeypatch.setenv("LOG_MAX_BYTES", str(DEFAULT_LOG_MAX_BYTES))
    monkeypatch.setenv("LOG_BACKUP_COUNT", str(DEFAULT_LOG_BACKUP_COUNT))
    monkeypatch.setenv("LOG_DIR", DEFAULT_LOG_DIR)
    monkeypatch.setenv("SCREENSHOT_ENABLED", str(DEFAULT_SCREENSHOT_ENABLED).lower())
    monkeypatch.setenv("SCREENSHOT_DIR", DEFAULT_SCREENSHOT_DIR)
    monkeypatch.setenv("MAX_CONCURRENT_REQUESTS", str(DEFAULT_MAX_CONCURRENT_REQUESTS))
    monkeypatch.setenv("LLM_MAX_TOKENS", str(DEFAULT_LLM_MAX_TOKENS))
    monkeypatch.setenv("LLM_TEMPERATURE", str(DEFAULT_LLM_TEMPERATURE))
    monkeypatch.setenv("REQUEST_TIMEOUT", str(DEFAULT_REQUEST_TIMEOUT))
    monkeypatch.setenv("AGENT_MODE", str(DEFAULT_AGENT_MODE))
    monkeypatch.setenv("VERBOSE", str(DEFAULT_VERBOSE))
    monkeypatch.setenv("RETRY_ATTEMPTS", str(DEFAULT_RETRY_ATTEMPTS))
    monkeypatch.setenv("RETRY_BACKOFF_MIN", str(DEFAULT_RETRY_BACKOFF_MIN))
    monkeypatch.setenv("RETRY_BACKOFF_MAX", str(DEFAULT_RETRY_BACKOFF_MAX))
    monkeypatch.setenv("DUMP_LLM_JSON_DIR", DEFAULT_DUMP_LLM_JSON_DIR)
    monkeypatch.setenv("DEBUG", str(DEFAULT_DEBUG_MODE))
    yield

@pytest.fixture(autouse=True)
def clear_agentic_env(monkeypatch: MonkeyPatch) -> None:
    """Unset all environment variables related to agentic_scraper."""
    for var in [
        "OPENAI_API_KEY",
        "ENV",
        "OPENAI_MODEL",
        "LOG_LEVEL",
        "LOG_FORMAT",
        "LOG_MAX_BYTES",
        "LOG_BACKUP_COUNT",
        "LOG_DIR",
        "SCREENSHOT_ENABLED",
        "SCREENSHOT_DIR",
        "MAX_CONCURRENT_REQUESTS",
        "LLM_MAX_TOKENS",
        "LLM_TEMPERATURE",
        "REQUEST_TIMEOUT",
        "RETRY_ATTEMPTS",
        "RETRY_BACKOFF_MIN",
        "RETRY_BACKOFF_MAX",
        "AGENT_MODE",
        "DUMP_LLM_JSON_DIR",
        "DEBUG",
        "VERBOSE",
    ]:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def reset_settings_cache() -> Generator[None, None, None]:
    """Reset the `get_settings()` cache before and after test."""
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest.fixture
def reload_settings(monkeypatch: MonkeyPatch) -> Callable[[dict[str, str]], None]:
    """Reload settings with environment overrides."""
    def _reload(env_vars: dict[str, str]) -> None:
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)
        settings_module.get_settings.cache_clear()
        importlib.reload(settings_module)
    return _reload


@pytest.fixture
def set_env_var(monkeypatch: MonkeyPatch) -> Callable[[str, str], None]:
    """Convenience fixture to patch a single env var."""
    return monkeypatch.setenv

# ---------------------------------------------------------------------
# Logging Capture
# ---------------------------------------------------------------------

@pytest.fixture
def log_stream() -> StringIO:
    """StringIO buffer for capturing logging output."""
    return StringIO()


@pytest.fixture
def debug_logger(log_stream: StringIO) -> logging.Logger:
    """Logger configured to write DEBUG logs to `log_stream`."""
    logger = logging.getLogger("agentic_scraper")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.handlers.clear()
    logger.addHandler(handler)
    return logger
