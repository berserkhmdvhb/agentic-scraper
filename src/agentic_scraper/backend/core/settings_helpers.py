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

TRUE_STRINGS: set[str] = {"1", "true", "yes", "on"}


def str_to_bool(s: str) -> bool:
    return s.strip().lower() in TRUE_STRINGS


def parse_str_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def safe_int(s: str) -> int:
    # Accept strings like "5", "5.0"
    return int(float(s))


def _coerce_and_validate(
    values: dict[str, Any],
    key: str,
    coerce_fn: Callable[[str], Any],
    validator: Callable[[Any], Any],
) -> None:
    """
    If key exists in values, coerce it from str (when applicable), run validator,
    and either set the validated value or raise. Empty strings are treated as omitted.
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
    _coerce_and_validate(values, "openai_model", str, validate_openai_model)


def _validate_optional_float(
    values: dict[str, Any], key: str, validator: Callable[[float], float]
) -> None:
    _coerce_and_validate(values, key, float, validator)


def _validate_optional_int(
    values: dict[str, Any], key: str, validator: Callable[[int], int]
) -> None:
    _coerce_and_validate(values, key, safe_int, validator)


def _validate_optional_str(
    values: dict[str, Any], key: str, validator: Callable[[str], str]
) -> None:
    _coerce_and_validate(values, key, str, validator)


def _validate_optional_path(values: dict[str, Any], key: str) -> None:
    _coerce_and_validate(values, key, str, lambda v: str(validate_path(v)))


def _validate_optional_bool(
    values: dict[str, Any], key: str, validator: Callable[[bool], bool]
) -> None:
    _coerce_and_validate(values, key, str_to_bool, validator)


def _validate_optional_list(
    values: dict[str, Any],
    key: str,
    validator: Callable[[list[str]], list[str]],
) -> None:
    _coerce_and_validate(values, key, parse_str_list, validator)


def _bridge_aliases(values: dict[str, Any]) -> None:
    """
    Copy known validation_alias environment keys (UPPER_SNAKE) to their field names
    (lowercase) so that 'mode="before"' validation sees them.
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
            # Always let explicit alias input override the field-value,
            # because this runs before Pydantic maps aliases.
            values[field] = values[alias]


def validated_settings(values: dict[str, Any]) -> dict[str, Any]:
    """
    Coerce & validate raw incoming settings (e.g., env vars) prior to model instantiation.
    Prefer pydantic-native constraints when possible; use centralized validators to normalize and
    keep behavior consistent across the project.
    """
    # Ensure env-style aliases are visible to the 'before' validator.
    _bridge_aliases(values)

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

    # Strict numeric validations that rely on constants; raise if out of range (do not clamp)
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
