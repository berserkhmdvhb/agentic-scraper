import logging
from collections.abc import Callable
from typing import Any

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_SETTING_OVERRIDDEN,
    MSG_DEBUG_SETTING_SKIPPED,
    MSG_WARNING_SETTING_INVALID,
)
from agentic_scraper.backend.utils.validators import (
    validate_concurrency,
    validate_log_backup_count,
    validate_log_level,
    validate_log_max_bytes,
    validate_max_tokens,
    validate_openai_model,
    validate_path,
    validate_temperature,
    validate_timeout,
)

logger = logging.getLogger(__name__)


def _validate_optional_model(values: dict[str, Any]) -> None:
    key = "openai_model"
    v = values.get(key, "").strip()
    if v:
        try:
            validated = validate_openai_model(v)
            values[key] = validated
            logger.debug(
                MSG_DEBUG_SETTING_OVERRIDDEN.format(key=key, validated=validated, original=v)
            )
        except ValueError as e:
            logger.warning(MSG_WARNING_SETTING_INVALID.format(key=key, original=v, error=e))
            raise
    else:
        logger.debug(MSG_DEBUG_SETTING_SKIPPED.format(key=key))
        values.pop(key, None)


def _validate_optional_float(
    values: dict[str, Any],
    key: str,
    validator: Callable[[float], float],
) -> None:
    v = values.get(key, "").strip()
    if v:
        try:
            coerced = float(v)
            validated = validator(coerced)
            values[key] = validated
            logger.debug(
                MSG_DEBUG_SETTING_OVERRIDDEN.format(key=key, validated=validated, original=v)
            )
        except ValueError as e:
            logger.warning(MSG_WARNING_SETTING_INVALID.format(key=key, original=v, error=e))
            raise
    else:
        logger.debug(MSG_DEBUG_SETTING_SKIPPED.format(key=key))
        values.pop(key, None)


def _validate_optional_int(
    values: dict[str, Any],
    key: str,
    validator: Callable[[int], int],
) -> None:
    v = values.get(key, "").strip()
    if v:
        try:
            coerced = int(v)
            validated = validator(coerced)
            values[key] = validated
            logger.debug(
                MSG_DEBUG_SETTING_OVERRIDDEN.format(key=key, validated=validated, original=v)
            )
        except ValueError as e:
            logger.warning(MSG_WARNING_SETTING_INVALID.format(key=key, original=v, error=e))
            raise
    else:
        logger.debug(MSG_DEBUG_SETTING_SKIPPED.format(key=key))
        values.pop(key, None)


def _validate_optional_str(
    values: dict[str, Any],
    key: str,
    validator: Callable[[str], str],
) -> None:
    v = values.get(key, "").strip()
    if v:
        try:
            validated = validator(v)
            values[key] = validated
            logger.debug(
                MSG_DEBUG_SETTING_OVERRIDDEN.format(key=key, validated=validated, original=v)
            )
        except ValueError as e:
            logger.warning(MSG_WARNING_SETTING_INVALID.format(key=key, original=v, error=e))
            raise
    else:
        logger.debug(MSG_DEBUG_SETTING_SKIPPED.format(key=key))
        values.pop(key, None)


def _validate_optional_path(values: dict[str, Any], key: str) -> None:
    v = values.get(key, "").strip()
    if v:
        try:
            resolved = str(validate_path(v))
            values[key] = resolved
            logger.debug(
                MSG_DEBUG_SETTING_OVERRIDDEN.format(key=key, validated=resolved, original=v)
            )
        except Exception as e:
            logger.warning(MSG_WARNING_SETTING_INVALID.format(key=key, original=v, error=e))
            raise
    else:
        logger.debug(MSG_DEBUG_SETTING_SKIPPED.format(key=key))
        values.pop(key, None)


def validated_settings(values: dict[str, Any]) -> dict[str, Any]:
    _validate_optional_model(values)
    _validate_optional_float(values, "llm_temperature", validate_temperature)
    _validate_optional_int(values, "llm_max_tokens", validate_max_tokens)
    _validate_optional_int(values, "max_concurrent_requests", validate_concurrency)
    _validate_optional_int(values, "request_timeout", validate_timeout)
    _validate_optional_str(values, "log_level", validate_log_level)
    _validate_optional_int(values, "log_max_bytes", validate_log_max_bytes)
    _validate_optional_int(values, "log_backup_count", validate_log_backup_count)
    _validate_optional_path(values, "log_dir")
    _validate_optional_path(values, "screenshot_dir")
    return values
