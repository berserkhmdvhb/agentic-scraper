import logging
from pathlib import Path
from urllib.parse import urlparse

from agentic_scraper.backend.config.constants import (
    FETCH_ERROR_PREFIX,
    LLM_MAX_TOKENS_LIMIT,
    LLM_TEMPERATURE_MAX,
    LLM_TEMPERATURE_MIN,
    MAX_CONCURRENCY_HARD_LIMIT,
    VALID_AGENT_MODES,
    VALID_ENVIRONMENTS,
    VALID_LOG_LEVELS,
    VALID_OPENAI_MODELS,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_SKIPPED_INVALID_URL,
    MSG_ERROR_EMPTY_STRING,
    MSG_ERROR_INVALID_AGENT_MODE,
    MSG_ERROR_INVALID_BACKUP_COUNT,
    MSG_ERROR_INVALID_CONCURRENCY,
    MSG_ERROR_INVALID_ENV,
    MSG_ERROR_INVALID_LOG_BYTES,
    MSG_ERROR_INVALID_LOG_LEVEL,
    MSG_ERROR_INVALID_MODEL_NAME,
    MSG_ERROR_INVALID_PRICE,
    MSG_ERROR_INVALID_TEMPERATURE,
    MSG_ERROR_INVALID_TIMEOUT,
    MSG_ERROR_INVALID_TOKENS,
    MSG_ERROR_NOT_A_DIRECTORY,
)

logger = logging.getLogger(__name__)


def format_with_valid_options(
    template: str,
    value_label: str,
    value: str,
    valid_values: set[str],
) -> str:
    return template.format(
        **{value_label: value},
        valid_options=", ".join(sorted(valid_values)),
    )


def is_valid_url(url: str) -> bool:
    """
    Check if a given string is a valid HTTP/HTTPS URL.

    Args:
        url (str): The URL to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def clean_input_urls(raw: str) -> list[str]:
    """
    Process raw input text (from textarea or file) into a list of cleaned URLs.

    Args:
        raw (str): Multi-line string with one or more URLs.

    Returns:
        list[str]: List of valid, stripped URLs.
    """
    lines = raw.strip().splitlines()
    cleaned = [line.strip() for line in lines if line.strip()]

    valid_urls = []
    for url in cleaned:
        if is_valid_url(url):
            valid_urls.append(url)
        else:
            logger.debug(MSG_DEBUG_SKIPPED_INVALID_URL.format(url=url))

    return valid_urls


def deduplicate_urls(urls: list[str]) -> list[str]:
    """
    Remove duplicate URLs while preserving order.

    Args:
        urls (list[str]): Input list of URLs.

    Returns:
        list[str]: Unique URLs in original order.
    """
    seen = set()
    result = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def filter_successful(results: dict[str, str]) -> dict[str, str]:
    """
    Filter out URLs where fetching failed (error string prefixed with __FETCH_ERROR__).

    Args:
        results (dict[str, str]): Map of url → html or error message.

    Returns:
        dict[str, str]: Only successfully fetched URLs.
    """
    return {url: html for url, html in results.items() if not html.startswith(FETCH_ERROR_PREFIX)}


###################

# ---------------------------------------------------------------------
# core/
# ---------------------------------------------------------------------

# settings.py


def validate_openai_model(model: str) -> str:
    if model not in VALID_OPENAI_MODELS:
        raise ValueError(
            format_with_valid_options(
                MSG_ERROR_INVALID_MODEL_NAME,
                value_label="model",
                value=model,
                valid_values=VALID_OPENAI_MODELS,
            )
        )
    return model


def validate_temperature(temp: float) -> float:
    if not (LLM_TEMPERATURE_MIN <= temp <= LLM_TEMPERATURE_MAX):
        raise ValueError(MSG_ERROR_INVALID_TEMPERATURE.format(value=temp))
    return temp


def validate_max_tokens(tokens: int) -> int:
    if not (0 < tokens <= LLM_MAX_TOKENS_LIMIT):
        raise ValueError(MSG_ERROR_INVALID_TOKENS.format(value=tokens))
    return tokens


def validate_concurrency(concurrency: int) -> int:
    if not (0 < concurrency <= MAX_CONCURRENCY_HARD_LIMIT):
        raise ValueError(MSG_ERROR_INVALID_CONCURRENCY.format(value=concurrency))
    return concurrency


def validate_timeout(seconds: int) -> int:
    if seconds <= 0:
        raise ValueError(MSG_ERROR_INVALID_TIMEOUT.format(value=seconds))
    return seconds


def validate_log_level(level: str) -> str:
    level = level.upper()
    if level not in VALID_LOG_LEVELS:
        raise ValueError(
            format_with_valid_options(
                MSG_ERROR_INVALID_LOG_LEVEL,
                value_label="value",
                value=level,
                valid_values=VALID_LOG_LEVELS,
            )
        )
    return level


def validate_log_max_bytes(n: int) -> int:
    if n <= 0:
        raise ValueError(MSG_ERROR_INVALID_LOG_BYTES.format(value=n))
    return n


def validate_log_backup_count(n: int) -> int:
    if n < 0:
        raise ValueError(MSG_ERROR_INVALID_BACKUP_COUNT.format(value=n))
    return n


def validate_path(path_str: str) -> Path:
    return Path(path_str).resolve()


def validate_env(env: str) -> str:
    if env.upper() not in VALID_ENVIRONMENTS:
        raise ValueError(
            format_with_valid_options(
                MSG_ERROR_INVALID_ENV,
                "value",
                env,
                VALID_ENVIRONMENTS,
            )
        )
    return env.upper()


def validate_optional_str(value: str | None, field_name: str = "value") -> str | None:
    if value is None:
        return None
    if value.strip() == "":
        raise ValueError(MSG_ERROR_EMPTY_STRING.format(field=field_name))
    return value


def validate_price(value: float | None) -> float | None:
    """Ensure price is non-negative if present."""
    if value is not None and value < 0:
        raise ValueError(MSG_ERROR_INVALID_PRICE.format(value=value))
    return value


def ensure_directory(path: Path) -> Path:
    path = path.resolve()
    if path.exists() and not path.is_dir():
        raise ValueError(MSG_ERROR_NOT_A_DIRECTORY % path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_agent_mode(mode: str) -> str:
    mode = mode.strip().lower()
    if mode not in VALID_AGENT_MODES:
        raise ValueError(
            format_with_valid_options(
                MSG_ERROR_INVALID_AGENT_MODE,
                "value",
                mode,
                VALID_AGENT_MODES,
            )
        )
    return mode
