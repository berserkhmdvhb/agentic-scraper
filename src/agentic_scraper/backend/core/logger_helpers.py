"""
Logging helpers: filters and formatters for environment-aware and structured logs.

Responsibilities:
- Enrich log records with the current environment (`DEV`, `UAT`, `PROD`, ...).
- Provide safe text formatting that tolerates missing record attributes.
- Provide JSON-structured logging with ISO 8601 timestamps and optional traceback.

Public API:
- `EnvironmentFilter`: Logging filter that injects `env` into every record.
- `SafeFormatter`: Defensive formatter that ensures `env` is always present.
- `JSONFormatter`: Structured formatter producing JSON logs with optional extras.

Usage:
    import logging
    from agentic_scraper.backend.core.logger_helpers import EnvironmentFilter, JSONFormatter

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    handler.addFilter(EnvironmentFilter())
    logging.getLogger().addHandler(handler)

Notes:
- `JSONFormatter` inspects `record.extra` if present and merges dict keys into the log.
- `SafeFormatter` ensures fallback `env="UNKNOWN"` if filter not applied.
- Timestamps are formatted in ISO 8601 (UTC-naive, local time zone).
"""

import json
import time
from logging import Filter, Formatter, LogRecord
from typing import Literal

from agentic_scraper.backend.core.settings import get_environment

__all__ = [
    "EnvironmentFilter",
    "JSONFormatter",
    "SafeFormatter",
]


class EnvironmentFilter(Filter):
    """Inject the current environment (e.g., DEV, UAT, PROD) into log records."""

    def filter(self, record: LogRecord) -> bool:
        record.env = get_environment()
        return True


class SafeFormatter(Formatter):
    """Formatter that substitutes missing LogRecord attributes with defaults."""

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: Literal["%", "{", "$"] = "%",
    ) -> None:
        """
        Initialize a safe formatter.

        Args:
            fmt (str | None): Log message format string.
            datefmt (str | None): Datetime format string.
            style (Literal["%", "{", "$"]): Format style (default "%").
        """
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)

    def format(self, record: LogRecord) -> str:
        """
        Format the log record, ensuring `env` is always present.

        Args:
            record (LogRecord): The log record.

        Returns:
            str: The formatted log message.
        """
        record.env = getattr(record, "env", "UNKNOWN")
        return super().format(record)


class JSONFormatter(Formatter):
    """Formatter for structured JSON logs with optional traceback and extra fields."""

    def format(self, record: LogRecord) -> str:
        """
        Format the log record as structured JSON.

        Args:
            record (LogRecord): The log record.

        Returns:
            str: JSON-encoded log string.
        """
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "env": getattr(record, "env", "UNKNOWN"),
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include traceback if available
        if record.exc_info:
            log_record["traceback"] = self.formatException(record.exc_info)

        # Include additional user-defined fields if present
        extra_fields = getattr(record, "extra", None)
        if isinstance(extra_fields, dict):
            log_record.update(extra_fields)

        return json.dumps(log_record, ensure_ascii=False)

    def formatTime(  # noqa: N802 - override name
        self, record: LogRecord, _datefmt: str | None = None
    ) -> str:
        """
        Format the record timestamp in ISO 8601 (local time).

        Args:
            record (LogRecord): The log record.
            _datefmt (str | None): Ignored; always returns ISO 8601.

        Returns:
            str: Formatted timestamp (YYYY-MM-DDTHH:MM:SS).
        """
        ct = self.converter(record.created)
        return time.strftime("%Y-%m-%dT%H:%M:%S", ct)
