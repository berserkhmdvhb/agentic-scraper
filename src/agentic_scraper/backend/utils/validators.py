import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from agentic_scraper.backend.config.constants import (
    FETCH_ERROR_PREFIX,
    MIN_ENCRYPTION_SECRET_LENGTH,
    VALID_AGENT_MODES,
    VALID_AUTH0_ALGORITHMS,
    VALID_ENVIRONMENTS,
    VALID_LOG_LEVELS,
    VALID_OPENAI_MODELS,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_SKIPPED_INVALID_URL,
    MSG_ERROR_BACKOFF_MIN_GREATER_THAN_MAX,
    MSG_ERROR_EMPTY_AUTH0_ALGORITHMS,
    MSG_ERROR_EMPTY_STRING,
    MSG_ERROR_INVALID_AGENT_MODE,
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
)

logger = logging.getLogger(__name__)


def format_with_valid_options(
    template: str,
    value_label: str,
    value: str,
    valid_values: set[str],
) -> str:
    """Format an error message with the given value and allowed options."""
    return template.format(
        **{value_label: value},
        valid_options=", ".join(sorted(valid_values)),
    )


def is_valid_url(url: str) -> bool:
    """Check if a string is a valid HTTP/HTTPS URL."""
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def clean_input_urls(raw: str) -> list[str]:
    """Split and clean raw multiline input into a list of valid URLs."""
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
    """Remove duplicates from a list of URLs, preserving order."""
    seen = set()
    result = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def filter_successful(results: dict[str, str]) -> dict[str, str]:
    """Filter out entries that contain fetch errors."""
    return {url: html for url, html in results.items() if not html.startswith(FETCH_ERROR_PREFIX)}


###################

# ---------------------------------------------------------------------
# core/
# ---------------------------------------------------------------------

# settings.py


def validate_openai_model(model: str) -> str:
    """Ensure the OpenAI model string is among supported values."""
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


def validate_timeout(seconds: int) -> int:
    """Ensure timeout value is a positive integer."""
    if seconds <= 0:
        raise ValueError(MSG_ERROR_INVALID_TIMEOUT.format(value=seconds))
    return seconds


def validate_log_level(level: str) -> str:
    """Ensure log level is valid (e.g., DEBUG, INFO)."""
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
    """Ensure max log file size is positive."""
    if n <= 0:
        raise ValueError(MSG_ERROR_INVALID_LOG_BYTES.format(value=n))
    return n


def validate_log_backup_count(n: int) -> int:
    """Ensure log backup count is non-negative."""
    if n < 0:
        raise ValueError(MSG_ERROR_INVALID_BACKUP_COUNT.format(value=n))
    return n


def validate_path(path_str: str) -> Path:
    """Convert a string to an absolute resolved Path."""
    return Path(path_str).resolve()


def validate_env(env: str) -> str:
    """Ensure the environment is one of the supported values."""
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
    """Ensure optional string is not empty if present."""
    if value is None:
        return None
    if value.strip() == "":
        raise ValueError(MSG_ERROR_EMPTY_STRING.format(field=field_name))
    return value


def validate_price(value: float | None) -> float | None:
    """Ensure price is non-negative, if provided."""
    if value is not None and value < 0:
        raise ValueError(MSG_ERROR_INVALID_PRICE.format(value=value))
    return value


def ensure_directory(path: Path) -> Path:
    """Ensure the given path exists and is a directory."""
    path = path.resolve()
    if path.exists() and not path.is_dir():
        raise ValueError(MSG_ERROR_NOT_A_DIRECTORY % path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_agent_mode(mode: str) -> str:
    """Ensure the agent mode is one of the valid options."""
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


def validate_openai_api_key(api_key: str | None) -> str:
    """Raise error if API key is missing or invalid."""
    if api_key in (None, "", "<<MISSING>>"):
        raise ValueError(MSG_ERROR_MISSING_API_KEY)
    return str(api_key)


def validate_or_create_dir(path_str: str) -> str:
    """Ensure the path is a directory, create if missing."""
    path = Path(path_str)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    elif not path.is_dir():
        raise ValueError(MSG_ERROR_NOT_A_DIRECTORY.format(path_str))
    return str(path.resolve())


def validate_log_rotation_config(max_bytes: int, backup_count: int) -> None:
    """Validate that log rotation parameters are compatible."""
    if max_bytes > 0 and backup_count <= 0:
        raise ValueError(MSG_ERROR_LOG_BACKUP_COUNT_INVALID)


def validate_backoff_range(min_backoff: float, max_backoff: float) -> None:
    """Ensure min backoff does not exceed max."""
    if min_backoff > max_backoff:
        raise ValueError(
            MSG_ERROR_BACKOFF_MIN_GREATER_THAN_MAX.format(min=min_backoff, max=max_backoff)
        )


def clean_price(v: str | float | None) -> float | str | None:
    """Parse and sanitize a price string or float."""
    if isinstance(v, str):
        cleaned = re.sub(r"[^\d.,-]", "", v)
        cleaned = cleaned.replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            raise ValueError(MSG_ERROR_INVALID_PRICE_FORMAT.format(value=v)) from None
    return v


def validate_auth0_domain(domain: str) -> str:
    """Ensure the Auth0 domain is syntactically valid."""
    if not domain or "." not in domain:
        raise ValueError(MSG_ERROR_INVALID_AUTH0_DOMAIN)
    return domain.strip()


def validate_api_audience(audience: str) -> str:
    """Ensure the API audience starts with 'http'."""
    if not audience.startswith("http"):
        raise ValueError(MSG_ERROR_INVALID_API_AUDIENCE)
    return audience.rstrip("/")


def validate_encryption_secret(secret: str) -> str:
    """Ensure encryption secret meets length requirements."""
    if len(secret.strip()) < MIN_ENCRYPTION_SECRET_LENGTH:
        raise ValueError(
            MSG_ERROR_INVALID_ENCRYPTION_SECRET.format(value=MIN_ENCRYPTION_SECRET_LENGTH)
        )
    return secret.strip()


def validate_auth0_algorithms(value: list[str]) -> list[str]:
    """Ensure provided Auth0 algorithms are in the allowed list."""
    if not value:
        raise ValueError(MSG_ERROR_EMPTY_AUTH0_ALGORITHMS)

    invalid = [alg for alg in value if alg not in VALID_AUTH0_ALGORITHMS]
    if invalid:
        raise ValueError(
            MSG_ERROR_INVALID_AUTH0_ALGORITHMS.format(
                algo=", ".join(invalid),
                valid_options=", ".join(sorted(VALID_AUTH0_ALGORITHMS)),
            )
        )
    return value
