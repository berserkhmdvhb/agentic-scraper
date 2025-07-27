import logging
from collections.abc import Callable
from typing import Any

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

TRUE_STRINGS = {"1", "true", "yes", "on"}


def str_to_bool(s: str) -> bool:
    return s.strip().lower() in TRUE_STRINGS


def parse_str_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def safe_int(s: str) -> int:
    return int(float(s))  # handles "5.0" gracefully


def _coerce_and_validate(
    values: dict[str, Any],
    key: str,
    coerce_fn: Callable[[str], Any],
    validator: Callable[[Any], Any],
) -> None:
    if key not in values:
        return

    raw = values[key]

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
    else:
        logger.debug(MSG_DEBUG_SETTING_SKIPPED.format(key=key))


def _validate_optional_openai_model(values: dict[str, Any]) -> None:
    """Validate the OpenAI model string (from env or override)."""
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


def validated_settings(values: dict[str, Any]) -> dict[str, Any]:
    """Main entry point to validate incoming Settings values before instantiating."""

    _validate_optional_openai_model(values)
    _validate_optional_int(values, "request_timeout", validate_timeout)
    _validate_optional_str(values, "log_level", validate_log_level)
    _validate_optional_int(values, "log_max_bytes", validate_log_max_bytes)
    _validate_optional_int(values, "log_backup_count", validate_log_backup_count)
    _validate_optional_path(values, "log_dir")
    _validate_optional_path(values, "screenshot_dir")
    _validate_optional_path(values, "dump_llm_json_dir")
    _validate_optional_str(values, "agent_mode", validate_agent_mode)
    _validate_optional_bool(values, "verbose", lambda v: v)  # no-op validator
    _validate_optional_str(values, "auth0_domain", validate_auth0_domain)
    _validate_optional_str(values, "auth0_api_audience", validate_api_audience)
    _validate_optional_str(values, "encryption_secret", validate_encryption_secret)
    _validate_optional_list(values, "auth0_algorithms", validate_auth0_algorithms)

    return values
