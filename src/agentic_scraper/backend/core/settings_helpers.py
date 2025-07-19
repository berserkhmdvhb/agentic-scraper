from typing import Any

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


def validated_settings(values: dict[str, Any]) -> dict[str, Any]:
    values["openai_model"] = validate_openai_model(values.get("openai_model", ""))
    values["llm_temperature"] = validate_temperature(values.get("llm_temperature", 0.0))
    values["llm_max_tokens"] = validate_max_tokens(values.get("llm_max_tokens", 0))
    values["max_concurrent_requests"] = validate_concurrency(
        values.get("max_concurrent_requests", 0)
    )
    values["request_timeout"] = validate_timeout(values.get("request_timeout", 0))
    values["log_level"] = validate_log_level(values.get("log_level", ""))
    values["log_max_bytes"] = validate_log_max_bytes(values.get("log_max_bytes", 0))
    values["log_backup_count"] = validate_log_backup_count(values.get("log_backup_count", 0))
    values["log_dir"] = str(validate_path(values.get("log_dir", "")))
    values["screenshot_dir"] = str(validate_path(values.get("screenshot_dir", "")))
    return values
