"""
Helpers for normalizing and validating environment-driven settings before Pydantic parsing.

Responsibilities:
- Bridge env-style aliases (e.g., `AUTH0_DOMAIN`) into field names for pre-parse validation.
- Coerce primitive values from strings (bool/int/float/list/path) where appropriate.
- Apply centralized validators for consistency across the project.
- Enforce strict numeric bounds for specific settings that rely on project constants.

Public API:
- `validated_settings`: Coerce & validate raw inputs prior to `Settings` instantiation.
- `str_to_bool`: Truthy string → bool helper.
- `parse_str_list`: Comma-delimited string → list[str].
- `safe_int`: Lenient integer coercion (accepts "5", "5.0").
- (Internal) `_coerce_and_validate` and `_validate_optional_*` helpers.

Operational:
- Logging: Emits debug logs for overrides/skips and warnings for invalid inputs.
- Retries: None.
- Concurrency: Pure functions; no I/O or shared state mutation besides logging.

Usage:
    from agentic_scraper.backend.core.settings_helpers import validated_settings

    raw = {"AUTH0_DOMAIN": "example.us.auth0.com", "VERBOSE": "yes", "LLM_TEMPERATURE": "0.2"}
    normalized = validated_settings(raw)
    # pass `normalized` into Settings.model_validate()

Notes:
- Empty strings are treated as "unset" and skipped (removed) to allow defaults to apply.
- When both alias and field are present, the alias value wins during pre-validation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from agentic_scraper.backend.config.constants import (
    MAX_LLM_SCHEMA_RETRIES,
    MAX_LLM_TEMPERATURE,
    MIN_LLM_SCHEMA_RETRIES,
    MIN_LLM_TEMPERATURE,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_SETTING_OVERRIDDEN,
    MSG_DEBUG_SETTING_SKIPPED,
    MSG_WARNING_SETTING_INVALID,
)
from agentic_scraper.backend.utils.validators import (
    validate_agent_mode,
    validate_api_audience,
    validate_auth0_algorithms,
    validate_auth0_domain,
    validate_encryption_secret,
    validate_log_backup_count,
    validate_log_level,
    validate_log_max_bytes,
    validate_openai_model,
    validate_path,
    validate_timeout,
)

logger = logging.getLogger(__name__)

__all__ = [
    "parse_str_list",
    "safe_int",
    "str_to_bool",
    "validated_settings",
]

# Strings interpreted as truthy by `str_to_bool`.
TRUE_STRINGS: set[str] = {"1", "true", "yes", "on"}


def str_to_bool(s: str) -> bool:
    """
    Convert a user-provided string into a boolean.

    Args:
        s (str): Input string (e.g., "1", "true", "on").

    Returns:
        bool: True if the string is a known truthy token (case-insensitive), else False.
    """
    return s.strip().lower() in TRUE_STRINGS


def parse_str_list(raw: str) -> list[str]:
    """
    Split a comma-delimited string into a list of trimmed, non-empty entries.

    Args:
        raw (str): Source string (e.g., "RS256, ES256 ").

    Returns:
        list[str]: Cleaned list of items.
    """
    return [item.strip() for item in raw.split(",") if item.strip()]


def safe_int(s: str) -> int:
    """
    Coerce a string to an integer, tolerating float-like inputs.

    Accepts values like "5" or "5.0" and returns 5.

    Args:
        s (str): Input numeric string.

    Returns:
        int: Integer value after coercion.
    """
    # Accept strings like "5", "5.0"
    return int(float(s))


def _coerce_and_validate(
    values: dict[str, Any],
    key: str,
    coerce_fn: Callable[[str], Any],
    validator: Callable[[Any], Any],
) -> None:
    """
    If key exists in `values`, coerce it (when string), then validate and write back.

    Behavior:
        - If value is a list: validate directly.
        - If value is a string: strip; if empty → treat as unset (remove); else coerce+validate.
        - If value is any other type: validate directly.
        - On success, the validated value overwrites the original.
        - On validation failure, a warning is logged and the exception is re-raised.

    Args:
        values (dict[str, Any]): Mutable dict of raw settings.
        key (str): Target key to process.
        coerce_fn (Callable[[str], Any]): Function to coerce string inputs.
        validator (Callable[[Any], Any]): Validation function; should return the validated value.

    Raises:
        Exception: Propagates validator exceptions after logging.
    """
    if key not in values:
        return

    raw = values[key]

    # List input: validate as-is (e.g., ["RS256"])
    if isinstance(raw, list):
        try:
            validated = validator(raw)
            values[key] = validated
            logger.debug(
                MSG_DEBUG_SETTING_OVERRIDDEN.format(key=key, validated=validated, original=raw)
            )
        except Exception as e:
            logger.warning(MSG_WARNING_SETTING_INVALID.format(key=key, original=raw, error=e))
            raise
        return

    # String input: coerce and validate
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            # Empty string → treated as omitted; allow model defaults to apply.
            logger.debug(MSG_DEBUG_SETTING_SKIPPED.format(key=key))
            values.pop(key, None)
            return
        try:
            coerced = coerce_fn(stripped)
            validated = validator(coerced)
            values[key] = validated
            logger.debug(
                MSG_DEBUG_SETTING_OVERRIDDEN.format(key=key, validated=validated, original=raw)
            )
        except Exception as e:
            logger.warning(MSG_WARNING_SETTING_INVALID.format(key=key, original=raw, error=e))
            raise
        return

    # Any other type (int, float, bool, None): validate directly
    try:
        validated = validator(raw)
        values[key] = validated
        logger.debug(
            MSG_DEBUG_SETTING_OVERRIDDEN.format(key=key, validated=validated, original=raw)
        )
    except Exception as e:
        logger.warning(MSG_WARNING_SETTING_INVALID.format(key=key, original=raw, error=e))
        raise


def _validate_optional_openai_model(values: dict[str, Any]) -> None:
    """Coerce and validate `openai_model` if present."""
    _coerce_and_validate(values, "openai_model", str, validate_openai_model)


def _validate_optional_float(
    values: dict[str, Any], key: str, validator: Callable[[float], float]
) -> None:
    """Coerce string → float for `key` and validate if present."""
    _coerce_and_validate(values, key, float, validator)


def _validate_optional_int(
    values: dict[str, Any], key: str, validator: Callable[[int], int]
) -> None:
    """Coerce string → int for `key` (leniently via `safe_int`) and validate if present."""
    _coerce_and_validate(values, key, safe_int, validator)


def _validate_optional_str(
    values: dict[str, Any], key: str, validator: Callable[[str], str]
) -> None:
    """Validate a string setting if present (after trimming empties)."""
    _coerce_and_validate(values, key, str, validator)


def _validate_optional_path(values: dict[str, Any], key: str) -> None:
    """Validate a filesystem path-like setting if present (returns normalized str)."""
    _coerce_and_validate(values, key, str, lambda v: str(validate_path(v)))


def _validate_optional_bool(
    values: dict[str, Any], key: str, validator: Callable[[bool], bool]
) -> None:
    """Coerce string → bool for `key` using `str_to_bool` and validate if present."""
    _coerce_and_validate(values, key, str_to_bool, validator)


def _validate_optional_list(
    values: dict[str, Any],
    key: str,
    validator: Callable[[list[str]], list[str]],
) -> None:
    """Coerce comma-delimited string → list[str] for `key` and validate if present."""
    _coerce_and_validate(values, key, parse_str_list, validator)


def _bridge_aliases(values: dict[str, Any]) -> None:
    """
    Make env-style aliases available to pre-parse validators.

    Copies known UPPER_SNAKE env keys to their field names so that the
    `mode="before"` validator can see them. If both are present, the alias wins.
    """
    alias_map = {
        # Auth / security
        "AUTH0_DOMAIN": "auth0_domain",
        "AUTH0_ISSUER": "auth0_issuer",
        "AUTH0_CLIENT_ID": "auth0_client_id",
        "AUTH0_CLIENT_SECRET": "auth0_client_secret",
        "AUTH0_ALGORITHMS": "auth0_algorithms",
        "AUTH0_API_AUDIENCE": "auth0_api_audience",
        "ENCRYPTION_SECRET": "encryption_secret",
        # Domains / URLs
        "BACKEND_DOMAIN": "backend_domain",
        "FRONTEND_DOMAIN": "frontend_domain",
        "AUTH0_REDIRECT_URI": "auth0_redirect_uri",
        # Logging
        "LOG_LEVEL": "log_level",
        "LOG_MAX_BYTES": "log_max_bytes",
        "LOG_BACKUP_COUNT": "log_backup_count",
        "LOG_DIR": "log_dir",
        "DUMP_LLM_JSON_DIR": "dump_llm_json_dir",
        "SCREENSHOT_DIR": "screenshot_dir",
        # Behavior / misc
        "VERBOSE": "verbose",
        "AGENT_MODE": "agent_mode",
        "REQUEST_TIMEOUT": "request_timeout",
        "LLM_TEMPERATURE": "llm_temperature",
        "LLM_SCHEMA_RETRIES": "llm_schema_retries",
    }
    for alias, field in alias_map.items():
        if alias in values:
            # Let explicit alias input override the field value during pre-validation.
            values[field] = values[alias]


def validated_settings(values: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize and validate raw settings (e.g., environment variables) prior to model parsing.

    Steps:
        1. Bridge well-known env aliases into field names.
        2. Coerce and validate optional fields (bool/int/float/list/path/str).
        3. Enforce strict numeric bounds for select LLM-related fields.

    Args:
        values (dict[str, Any]): Raw settings mapping (mutated in-place).

    Returns:
        dict[str, Any]: The same mapping with normalized/validated values.

    Raises:
        ValueError: On invalid values (e.g., out-of-bounds temperature/retries).
        Exception: Propagates specific validator errors for upstream handling.

    Notes:
        - Empty strings are removed to allow model defaults to take effect.
        - No I/O is performed; this function is safe for early import-time use.
    """
    # Ensure env-style aliases are visible to the 'before' validator.
    _bridge_aliases(values)

    # Coerce+validate fields when optionally present.
    _validate_optional_openai_model(values)
    _validate_optional_int(values, "request_timeout", validate_timeout)
    _validate_optional_str(values, "log_level", validate_log_level)
    _validate_optional_int(values, "log_max_bytes", validate_log_max_bytes)
    _validate_optional_int(values, "log_backup_count", validate_log_backup_count)
    _validate_optional_path(values, "log_dir")
    _validate_optional_path(values, "screenshot_dir")
    _validate_optional_path(values, "dump_llm_json_dir")
    _validate_optional_str(values, "agent_mode", validate_agent_mode)
    _validate_optional_bool(values, "verbose", lambda v: v)  # pass-through after coercion
    _validate_optional_str(values, "auth0_domain", validate_auth0_domain)
    _validate_optional_str(values, "auth0_api_audience", validate_api_audience)
    _validate_optional_str(values, "encryption_secret", validate_encryption_secret)
    _validate_optional_list(values, "auth0_algorithms", validate_auth0_algorithms)

    # Strict numeric validations that rely on constants; raise if out of range (do not clamp).
    _validate_optional_float(
        values,
        "llm_temperature",
        lambda v: v
        if (MIN_LLM_TEMPERATURE <= v <= MAX_LLM_TEMPERATURE)
        else (_ for _ in ()).throw(ValueError(f"llm_temperature out of bounds: {v}")),
    )
    _validate_optional_int(
        values,
        "llm_schema_retries",
        lambda v: v
        if (MIN_LLM_SCHEMA_RETRIES <= v <= MAX_LLM_SCHEMA_RETRIES)
        else (_ for _ in ()).throw(ValueError(f"llm_schema_retries out of bounds: {v}")),
    )

    return values
