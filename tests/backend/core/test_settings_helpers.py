import logging
from typing import Any

import pytest

from agentic_scraper.backend.core.settings_helpers import (
    TRUE_STRINGS,
    parse_str_list,
    safe_int,
    str_to_bool,
    validated_settings,
    _coerce_and_validate,  # testing internals intentionally
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_SETTING_OVERRIDDEN,
    MSG_DEBUG_SETTING_SKIPPED,
    MSG_WARNING_SETTING_INVALID,
)


# ---------- Primitive helpers ----------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1", True),
        ("true", True),
        ("TrUe", True),
        ("yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("no", False),
        (" off ", False),
        ("", False),
        ("   ", False),
    ],
)
def test_str_to_bool(raw: str, expected: bool) -> None:
    assert str_to_bool(raw) is expected
    # sanity: TRUE_STRINGS covers the positive set
    if expected:
        assert raw.strip().lower() in TRUE_STRINGS or raw.strip().lower() == "1"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("a,b,c", ["a", "b", "c"]),
        (" a , b ,  c ", ["a", "b", "c"]),
        (",,x,,", ["x"]),
        ("", []),
        ("   ", []),
    ],
)
def test_parse_str_list(raw: str, expected: list[str]) -> None:
    assert parse_str_list(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("5", 5),
        ("5.0", 5),
        ("7.9", 7),   # int(float("7.9")) -> 7
        ("  10  ", 10),
    ],
)
def test_safe_int(raw: str, expected: int) -> None:
    assert safe_int(raw) == expected


# ---------- _coerce_and_validate (internal) ----------

def test__coerce_and_validate_string_ok(caplog: pytest.LogCaptureFixture) -> None:
    values: dict[str, Any] = {"log_level": "info"}

    def coerce(s: str) -> str:  # identity coercion
        return s

    def validator(v: str) -> str:
        assert isinstance(v, str)
        return v.upper()

    caplog.set_level(logging.DEBUG)
    _coerce_and_validate(values, "log_level", coerce, validator)
    assert values["log_level"] == "INFO"
    assert any(MSG_DEBUG_SETTING_OVERRIDDEN.split("{")[0] in rec.message for rec in caplog.records)


def test__coerce_and_validate_list_ok(caplog: pytest.LogCaptureFixture) -> None:
    values: dict[str, Any] = {"auth0_algorithms": ["RS256", "ES256"]}

    def coerce_list(_: str) -> list[str]:
        raise AssertionError("should not be called for list input")

    def validator(v: list[str]) -> list[str]:
        assert isinstance(v, list)
        return [x.upper() for x in v]

    caplog.set_level(logging.DEBUG)
    _coerce_and_validate(values, "auth0_algorithms", coerce_list, validator)
    assert values["auth0_algorithms"] == ["RS256", "ES256"]
    assert any(MSG_DEBUG_SETTING_OVERRIDDEN.split("{")[0] in rec.message for rec in caplog.records)


def test__coerce_and_validate_empty_string_skips(caplog: pytest.LogCaptureFixture) -> None:
    values: dict[str, Any] = {"dump_llm_json_dir": "   "}

    def coerce(s: str) -> str:
        return s

    def validator(v: str) -> str:
        return v

    caplog.set_level(logging.DEBUG)
    _coerce_and_validate(values, "dump_llm_json_dir", coerce, validator)
    assert "dump_llm_json_dir" not in values
    assert any(MSG_DEBUG_SETTING_SKIPPED.split("{")[0] in rec.message for rec in caplog.records)


def test__coerce_and_validate_non_str_or_list_validates(caplog: pytest.LogCaptureFixture) -> None:
    values: dict[str, Any] = {"agent_mode": 123}

    def coerce(s: str) -> str:
        return s

    def validator(v: str) -> str:
        return v

    caplog.set_level(logging.DEBUG)
    _coerce_and_validate(values, "agent_mode", coerce, validator)
    # value validated and kept
    assert values["agent_mode"] == 123
    # now we expect an "overridden" log (since we validated non-str/list types)
    assert any(MSG_DEBUG_SETTING_OVERRIDDEN.split("{")[0] in rec.message for rec in caplog.records)


def test__coerce_and_validate_raises_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    values: dict[str, Any] = {"log_level": "WRONG"}

    def coerce(s: str) -> str:
        return s

    def validator(_: str) -> str:
        raise ValueError("bad level")

    caplog.set_level(logging.DEBUG)
    with pytest.raises(ValueError):
        _coerce_and_validate(values, "log_level", coerce, validator)

    assert any(MSG_WARNING_SETTING_INVALID.split("{")[0] in rec.message for rec in caplog.records)


# ---------- validated_settings (integration) ----------

def test_validated_settings_parses_csv_list_and_bool(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Patch the names used *inside* settings_helpers (not the validators module)
    monkeypatch.setattr(
        "agentic_scraper.backend.core.settings_helpers.validate_auth0_algorithms",
        lambda v: v,  # identity
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.core.settings_helpers.validate_log_level",
        lambda s: s,  # identity
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.core.settings_helpers.validate_log_max_bytes",
        int,  # accept ints
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.core.settings_helpers.validate_log_backup_count",
        int,  # accept ints
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.core.settings_helpers.validate_path",
        lambda p: p,  # identity
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.core.settings_helpers.validate_agent_mode",
        lambda s: s,  # identity
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.core.settings_helpers.validate_timeout",
        int,  # accept ints
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.core.settings_helpers.validate_openai_model",
        lambda s: s,  # identity
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.core.settings_helpers.validate_api_audience",
        lambda s: s,  # identity
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.core.settings_helpers.validate_auth0_domain",
        lambda s: s,  # identity
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.core.settings_helpers.validate_encryption_secret",
        lambda s: s,  # identity
    )

    values: dict[str, Any] = {
        "auth0_algorithms": "RS256, ES256  ,  HS256",
        "verbose": "YeS",
        "log_level": "debug",
        "log_max_bytes": "1048576",
        "log_backup_count": "5",
        "log_dir": "/tmp/logs",
        "dump_llm_json_dir": "/tmp/llm",
        "screenshot_dir": "/data/imgs",
        "agent_mode": "dynamic",
        "request_timeout": "30",
        "openai_model": "gpt-4o",
        "auth0_api_audience": "https://api.example.com",
        "auth0_domain": "test.auth0.com",
        "encryption_secret": "x" * 32,
    }

    caplog.set_level(logging.DEBUG)
    out = validated_settings(values)

    assert out["auth0_algorithms"] == ["RS256", "ES256", "HS256"]
    assert out["verbose"] is True
    assert out["log_level"] == "debug"
    assert out["log_max_bytes"] == 1048576
    assert out["log_backup_count"] == 5
    assert out["log_dir"] == "/tmp/logs"
    assert out["dump_llm_json_dir"] == "/tmp/llm"
    assert out["screenshot_dir"] == "/data/imgs"
    assert out["agent_mode"] == "dynamic"
    assert out["request_timeout"] == 30
    assert out["openai_model"] == "gpt-4o"
    # At least one "overridden" message should be in logs
    assert any(MSG_DEBUG_SETTING_OVERRIDDEN.split("{")[0] in rec.message for rec in caplog.records)


def test_validated_settings_empty_string_skips_key(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    # keep path validator simple
    monkeypatch.setattr(
        "agentic_scraper.backend.utils.validators.validate_path",
        lambda p: p,
    )

    values: dict[str, Any] = {"dump_llm_json_dir": "   "}
    caplog.set_level(logging.DEBUG)
    out = validated_settings(values)
    assert "dump_llm_json_dir" not in out
    assert any(MSG_DEBUG_SETTING_SKIPPED.split("{")[0] in rec.message for rec in caplog.records)


def test_validated_settings_list_input_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    # identity validator for auth0 algorithms
    monkeypatch.setattr(
        "agentic_scraper.backend.utils.validators.validate_auth0_algorithms",
        lambda v: v,
    )
    values: dict[str, Any] = {"auth0_algorithms": ["RS256"]}
    out = validated_settings(values)
    assert out["auth0_algorithms"] == ["RS256"]


def test_validated_settings_invalid_value_raises_and_logs_warning(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    def bad_level(_: str) -> str:
        raise ValueError("boom")

    monkeypatch.setattr(
        "agentic_scraper.backend.utils.validators.validate_log_level",
        bad_level,
    )
    values = {"log_level": "WRONG"}
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ValueError):
        validated_settings(values)

    assert any(MSG_WARNING_SETTING_INVALID.split("{")[0] in rec.message for rec in caplog.records)

def test__coerce_and_validate_non_str_or_list_raises_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    values: dict[str, Any] = {"llm_schema_retries": -1}

    def coerce(s: str) -> int:
        return int(s)

    def validator(v: int) -> int:
        raise ValueError("out of range")

    caplog.set_level(logging.DEBUG)
    with pytest.raises(ValueError):
        _coerce_and_validate(values, "llm_schema_retries", coerce, validator)
    assert any(MSG_WARNING_SETTING_INVALID.split("{")[0] in rec.message for rec in caplog.records)