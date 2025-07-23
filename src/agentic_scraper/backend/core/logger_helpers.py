import json
import time
from logging import Filter, Formatter, LogRecord
from typing import Literal

from agentic_scraper.backend.core.settings import get_environment


class EnvironmentFilter(Filter):
    """Injects the current environment (e.g., DEV, UAT, PROD) into log records."""

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
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)

    def format(self, record: LogRecord) -> str:
        record.env = getattr(record, "env", "UNKNOWN")
        return super().format(record)


class JSONFormatter(Formatter):
    """Formatter for structured JSON logs with optional traceback and extra fields."""

    def format(self, record: LogRecord) -> str:
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

    def formatTime(  # noqa: N802
        self, record: LogRecord, _datefmt: str | None = None
    ) -> str:
        """Format time as ISO 8601 timestamp."""
        ct = self.converter(record.created)
        return time.strftime("%Y-%m-%dT%H:%M:%S", ct)
