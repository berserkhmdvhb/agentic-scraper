import logging

from agentic_scraper.backend.core.logger_helpers import (
    CustomRotatingFileHandler,
    EnvironmentFilter,
    JSONFormatter,
    SafeFormatter,
)
from agentic_scraper.backend.core.settings import (
    get_log_backup_count,
    get_log_dir,
    get_log_format,
    get_log_level,
    get_log_max_bytes,
)

LOGGER_NAME = "agentic_scraper"


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def teardown_logger(logger: logging.Logger | None = None) -> None:
    logger = logger or get_logger()
    for handler in logger.handlers[:]:
        handler.flush()
        handler.close()
        logger.removeHandler(handler)


def setup_logging(
    *, reset: bool = False, return_handlers: bool = False
) -> list[logging.Handler] | None:
    logger = get_logger()

    if reset:
        teardown_logger(logger)

    if not reset and any(
        isinstance(h, (logging.StreamHandler, CustomRotatingFileHandler)) for h in logger.handlers
    ):
        return None  # Already configured

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    env_filter = EnvironmentFilter()
    fmt = "[%(asctime)s] [%(env)s] [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    formatter: logging.Formatter
    if get_log_format() == "json":
        formatter = JSONFormatter(datefmt=datefmt)
    else:
        formatter = SafeFormatter(fmt=fmt, datefmt=datefmt)

    # Console handler
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(get_log_level())
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(env_filter)
    logger.addHandler(stream_handler)

    # File handler
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "agentic_scraper.log"
    file_handler = CustomRotatingFileHandler(
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
