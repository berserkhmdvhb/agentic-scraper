import json
from io import TextIOWrapper
from logging import Filter, Formatter, LogRecord
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Literal, cast

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
    """Formatter for structured JSON logs."""

    def format(self, record: LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "env": getattr(record, "env", "UNKNOWN"),
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(log_record, ensure_ascii=False)


class CustomRotatingFileHandler(RotatingFileHandler):
    """
    Rotating file handler with safe UTF-8 encoding and optional future hooks
    for structured or DB-based logging.
    """

    def _open(self) -> TextIOWrapper:
        return cast(
            "TextIOWrapper", Path(self.baseFilename).open(self.mode, encoding=self.encoding)
        )

    def rotation_filename(self, default_name: str) -> str:
        """Return default filename; override later if custom naming is needed."""
        return default_name
