import logging
from logging.handlers import RotatingFileHandler

from agentic_scraper.config.constants import LOGGER_NAME
from agentic_scraper.core.logger_helpers import (
    EnvironmentFilter,
    JSONFormatter,
    SafeFormatter,
)
from agentic_scraper.core.settings import (
    get_log_backup_count,
    get_log_dir,
    get_log_format,
    get_log_level,
    get_log_max_bytes,
    get_settings,
)


def get_logger() -> logging.Logger:
    """
    Get the main logger instance used throughout the application.

    Returns:
        logging.Logger: The application-level logger with the configured name.
    """
    return logging.getLogger(LOGGER_NAME)


def teardown_logger(logger: logging.Logger | None = None) -> None:
    """
    Flush and remove all handlers from the specified logger.

    This is useful for resetting the logger during testing or before reinitializing.

    Args:
        logger (logging.Logger | None):
            Logger instance to clean up. If None, uses the default application logger.
    """
    logger = logger or get_logger()
    for handler in logger.handlers[:]:
        handler.flush()
        handler.close()
        logger.removeHandler(handler)


def setup_logging(
    *, reset: bool = False, return_handlers: bool = False
) -> list[logging.Handler] | None:
    """
    Set up logging for both console and rotating file output with structured formatting.

    This function initializes:
    - A console stream handler (level based on settings or verbose mode)
    - A rotating file handler (always logs DEBUG level)

    Applies consistent formatting, environment tagging, and log rotation settings.

    Args:
        reset (bool, optional): If True, clears existing handlers before setup. Defaults to False.
        return_handlers (bool, optional):
            If True, returns the installed handlers for testing or inspection.

    Returns:
        list[logging.Handler] | None:
            The created logging handlers if `return_handlers` is True, else None.
    """
    logger = get_logger()

    if reset:
        teardown_logger(logger)

    if not reset and any(
        isinstance(h, (logging.StreamHandler, RotatingFileHandler)) for h in logger.handlers
    ):
        return None

    settings = get_settings()
    log_level = logging.DEBUG if settings.is_verbose_mode else get_log_level()
    logger.setLevel(log_level)
    logger.propagate = False

    env_filter = EnvironmentFilter()
    fmt = "[%(asctime)s] [%(env)s] [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    formatter: logging.Formatter
    if get_log_format() == "json":
        formatter = JSONFormatter(datefmt=datefmt)
    else:
        formatter = SafeFormatter(fmt=fmt, datefmt=datefmt)

    # Console handler (uses same level as logger)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(env_filter)
    logger.addHandler(stream_handler)

    # File handler (always debug for detailed logs)
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "agentic_scraper.log"
    file_handler = RotatingFileHandler(
        filename=log_path,
        mode="a",
        maxBytes=get_log_max_bytes(),
        backupCount=get_log_backup_count(),
        encoding="utf-8",
        delay=False,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(env_filter)
    logger.addHandler(file_handler)

    if return_handlers:
        return [stream_handler, file_handler]

    return None
