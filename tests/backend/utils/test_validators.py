from __future__ import annotations

import logging
import io
import os
import re
from pathlib import Path
from typing import Iterable

import pytest
from _pytest.logging import LogCaptureFixture

from agentic_scraper.backend.config.constants import (
    FETCH_ERROR_PREFIX,
    MIN_ENCRYPTION_SECRET_LENGTH,
    VALID_AUTH0_ALGORITHMS,
    VALID_ENVIRONMENTS,
    VALID_LOG_LEVELS,
    VALID_OPENAI_MODELS,
)
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_BACKOFF_MIN_GREATER_THAN_MAX,
    MSG_ERROR_EMPTY_AUTH0_ALGORITHMS,
    MSG_ERROR_EMPTY_STRING,
    MSG_ERROR_INVALID_API_AUDIENCE,
    MSG_ERROR_INVALID_AUTH0_ALGORITHMS,
    MSG_ERROR_INVALID_AUTH0_DOMAIN,
    MSG_ERROR_INVALID_BACKUP_COUNT,
    MSG_ERROR_INVALID_ENCRYPTION_SECRET,
    MSG_ERROR_INVALID_ENV,
    MSG_ERROR_INVALID_LOG_BYTES,
    MSG_ERROR_INVALID_LOG_LEVEL,
    MSG_ERROR_INVALID_MODEL_NAME,
    MSG_ERROR_INVALID_PRICE,
    MSG_ERROR_INVALID_PRICE_FORMAT,
    MSG_ERROR_INVALID_TIMEOUT,
    MSG_ERROR_LOG_BACKUP_COUNT_INVALID,
    MSG_ERROR_MISSING_API_KEY,
    MSG_ERROR_NOT_A_DIRECTORY,
    MSG_ERROR_INVALID_AGENT_MODE,
    MSG_ERROR_INVALID_TIMEOUT,
)
from agentic_scraper.backend.config.types import AgentMode
import agentic_scraper.backend.utils.validators as v



# ------------------------------ small helpers ------------------------------- #

def _contains_any(s: str, parts: Iterable[str]) -> bool:
    return any(p in s for p in parts)


# ---------------------------------- URL utils -------------------------------- #

def test_deduplicate_urls_preserves_order() -> None:
    src = ["a", "b", "a", "c", "b", "d"]
    assert v.deduplicate_urls(src) == ["a", "b", "c", "d"]


def test_is_valid_url_and_clean_input_logs_invalid() -> None:
    good = "https://example.com/x"
    bad = "notaurl"

    assert v.is_valid_url(good) is True
    assert v.is_valid_url(bad) is False

    # Attach a temporary handler to the module logger
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.DEBUG)

    v.logger.setLevel(logging.DEBUG)
    v.logger.propagate = False  # ensure we only capture via our handler
    v.logger.addHandler(handler)
    try:
        urls = v.clean_input_urls(f"\n{good}\n{bad}\n  \nhttp://foo.bar \n")
    finally:
        v.logger.removeHandler(handler)

    assert urls == [good, "http://foo.bar"]

    # Assert the invalid URL was mentioned in the DEBUG log
    contents = buf.getvalue()
    assert "notaurl" in contents

def test_filter_successful_drops_error_prefix() -> None:
    results = {
        "u1": FETCH_ERROR_PREFIX + " timeout",
        "u2": "<html>ok</html>",
    }
    filtered = v.filter_successful(results)
    assert "u1" not in filtered and "u2" in filtered


# ------------------------------ settings validators -------------------------- #

def test_validate_openai_model_ok_and_error() -> None:
    # pick any valid model from constants
    model = next(iter(VALID_OPENAI_MODELS))
    assert v.validate_openai_model(model) == model

    with pytest.raises(ValueError) as e:
        v.validate_openai_model("nope")
    assert MSG_ERROR_INVALID_MODEL_NAME.split("{", 1)[0] in str(e.value)


def test_validate_timeout_positive() -> None:
    assert v.validate_timeout(5) == 5
    with pytest.raises(ValueError) as e:
        v.validate_timeout(0)
    assert str(e.value) == MSG_ERROR_INVALID_TIMEOUT.format(value=0)

def test_validate_log_level_case_insensitive() -> None:
    assert v.validate_log_level("debug") == "DEBUG"
    with pytest.raises(ValueError) as e:
        v.validate_log_level("LOUD")
    # includes valid options list
    assert _contains_any(str(e.value), ["DEBUG", "INFO", "WARNING", "ERROR"])  # from VALID_LOG_LEVELS
    assert v.format_with_valid_options(MSG_ERROR_INVALID_LOG_LEVEL, "value", "LOUD", VALID_LOG_LEVELS).split("{", 1)[0] in str(e.value)


def test_validate_log_max_bytes_and_backup_count() -> None:
    assert v.validate_log_max_bytes(1) == 1
    with pytest.raises(ValueError, match=re.escape(MSG_ERROR_INVALID_LOG_BYTES.format(value=0))):
        v.validate_log_max_bytes(0)

    assert v.validate_log_backup_count(0) == 0
    with pytest.raises(ValueError, match=re.escape(MSG_ERROR_INVALID_BACKUP_COUNT.format(value=-1))):
        v.validate_log_backup_count(-1)



def test_validate_path_returns_path() -> None:
    p = v.validate_path(".")
    assert isinstance(p, Path)
    assert p.is_absolute()


def test_validate_env_uppercases_and_errors() -> None:
    # pick any valid env and ensure uppercasing
    env_val = next(iter(VALID_ENVIRONMENTS))
    assert v.validate_env(env_val.lower()) == env_val

    with pytest.raises(ValueError) as e:
        v.validate_env("UNKNOWN")
    assert v.format_with_valid_options(MSG_ERROR_INVALID_ENV, "value", "UNKNOWN", VALID_ENVIRONMENTS).split("{", 1)[0] in str(e.value)

def test_validate_optional_str_rules() -> None:
    assert v.validate_optional_str(None) is None
    assert v.validate_optional_str(" ok ") == " ok "
    with pytest.raises(ValueError) as e:
        v.validate_optional_str("   ")
    assert str(e.value) == MSG_ERROR_EMPTY_STRING.format(field="value")


def test_validate_price_non_negative() -> None:
    assert v.validate_price(None) is None
    assert v.validate_price(0.0) == 0.0
    with pytest.raises(ValueError) as e:
        v.validate_price(-1.0)
    assert str(e.value) == MSG_ERROR_INVALID_PRICE.format(value=-1.0)


def test_ensure_directory_and_file_conflict(tmp_path: Path) -> None:
    # creates directory when missing
    target = tmp_path / "newdir"
    out = v.ensure_directory(target)
    assert out == target.resolve() and target.is_dir()

    # error if path exists as file
    file_path = tmp_path / "afile"
    file_path.write_text("x")
    with pytest.raises(ValueError) as e:
        v.ensure_directory(file_path)
    # MSG_ERROR_NOT_A_DIRECTORY may use % formatting in this function
    assert str(e.value) == MSG_ERROR_NOT_A_DIRECTORY.format(path=str(file_path.resolve()))


def test_validate_agent_mode_ok_and_error() -> None:
    # choose any valid mode from the enum
    mode_any = next(iter(AgentMode)).value
    assert v.validate_agent_mode(mode_any) == AgentMode(mode_any)

    with pytest.raises(ValueError) as e:
        v.validate_agent_mode("totally-unknown-mode")
    # should include allowed set; we just assert prefix
    assert MSG_ERROR_INVALID_AGENT_MODE.split("{", 1)[0] in str(e.value)


def test_validate_openai_api_key() -> None:
    assert v.validate_openai_api_key("sk-123") == "sk-123"
    for bad in (None, "", "<<MISSING>>"):
        with pytest.raises(ValueError) as e:
            v.validate_openai_api_key(bad)
        assert str(e.value) == MSG_ERROR_MISSING_API_KEY



def test_validate_or_create_dir(tmp_path: Path) -> None:
    d = tmp_path / "x" / "y"
    out = v.validate_or_create_dir(str(d))
    assert Path(out).is_dir()

    # conflict with file
    f = tmp_path / "file"
    f.write_text("x")
    with pytest.raises(ValueError) as e:
        v.validate_or_create_dir(str(f))
    assert MSG_ERROR_NOT_A_DIRECTORY.split("{")[0] in str(e.value)


def test_validate_log_rotation_config_rules() -> None:
    v.validate_log_rotation_config(max_bytes=0, backup_count=0)
    v.validate_log_rotation_config(max_bytes=10, backup_count=1)
    with pytest.raises(ValueError) as e:
        v.validate_log_rotation_config(max_bytes=10, backup_count=0)
    assert str(e.value) == MSG_ERROR_LOG_BACKUP_COUNT_INVALID


def test_validate_backoff_range() -> None:
    v.validate_backoff_range(0.1, 0.2)
    with pytest.raises(ValueError) as e:
        v.validate_backoff_range(2, 1)
    assert str(e.value) == MSG_ERROR_BACKOFF_MIN_GREATER_THAN_MAX.format(min=2, max=1)


def test_clean_price_parsing_and_errors() -> None:
    # strings
    assert v.clean_price("$1,234.50") == 1234.50
    assert v.clean_price("€ 99") == 99.0
    # floats passthrough
    assert v.clean_price(12.3) == 12.3
    # invalid
    with pytest.raises(ValueError) as e:
        v.clean_price("not a price")
    assert MSG_ERROR_INVALID_PRICE_FORMAT.split("{", 1)[0] in str(e.value)


def test_validate_auth0_domain_and_audience() -> None:
    assert v.validate_auth0_domain("example.com") == "example.com"
    with pytest.raises(ValueError) as e:
        v.validate_auth0_domain("invalid")
    assert str(e.value) == MSG_ERROR_INVALID_AUTH0_DOMAIN

    assert v.validate_api_audience("https://api.example.com/") == "https://api.example.com"
    with pytest.raises(ValueError) as e:
        v.validate_api_audience("api.example.com")
    assert str(e.value) == MSG_ERROR_INVALID_API_AUDIENCE


def test_validate_encryption_secret_length() -> None:
    ok = "x" * MIN_ENCRYPTION_SECRET_LENGTH
    assert v.validate_encryption_secret(ok) == ok
    with pytest.raises(ValueError) as e:
        v.validate_encryption_secret("short")
    assert str(e.value) == MSG_ERROR_INVALID_ENCRYPTION_SECRET.format(
        value=MIN_ENCRYPTION_SECRET_LENGTH
    )

def test_validate_auth0_algorithms_rules() -> None:
    # empty list
    with pytest.raises(ValueError) as e1:
        v.validate_auth0_algorithms([])
    assert str(e1.value) == MSG_ERROR_EMPTY_AUTH0_ALGORITHMS

    # invalid entries
    with pytest.raises(ValueError) as e2:
        v.validate_auth0_algorithms(["HS999"])
    assert MSG_ERROR_INVALID_AUTH0_ALGORITHMS.split("{", 1)[0] in str(e2.value)

    # all valid
    sample_valid = list(VALID_AUTH0_ALGORITHMS)[:1]
    assert v.validate_auth0_algorithms(sample_valid) == sample_valid
