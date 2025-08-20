import logging
from pathlib import Path
from typing import List

import pytest

from agentic_scraper.backend.core import logger_setup as ls


@pytest.fixture
def tmp_log_dir(tmp_path: Path) -> Path:
    d = tmp_path / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _cleanup_logger() -> None:
    # Ensure we leave the logger clean regardless of test outcome
    try:
        ls.teardown_logger()
    except Exception:
        pass


def test_setup_logging_installs_handlers_once(
    monkeypatch: pytest.MonkeyPatch, tmp_log_dir: Path
) -> None:
    # route logs to temp dir
    monkeypatch.setattr(ls, "get_log_dir", lambda: tmp_log_dir)
    # force plain format to exercise SafeFormatter branch
    monkeypatch.setattr(ls, "get_log_format", lambda: "plain")

    # use non-verbose path (so logger level comes from get_log_level)
    # also stub rotation settings to avoid calling get_settings() under the hood
    monkeypatch.setattr(ls, "get_log_max_bytes", lambda: 1024)
    monkeypatch.setattr(ls, "get_log_backup_count", lambda: 3)    
    monkeypatch.setattr(
        ls, "get_log_level", lambda: logging.INFO
    )
    monkeypatch.setattr(
        ls, "get_settings", lambda: type("S", (), {"is_verbose_mode": False})()
    )

    try:
        handlers = ls.setup_logging(reset=True, return_handlers=True)
        assert handlers is not None
        # Expect a stream handler + rotating file handler
        assert len(handlers) == 2
        assert any(isinstance(h, logging.StreamHandler) for h in handlers)
        assert any(h.__class__.__name__ == "RotatingFileHandler" for h in handlers)

        # Call again without reset: should be idempotent (no duplicate handlers)
        again = ls.setup_logging(reset=False, return_handlers=True)
        assert again is None  # function returns None if already set
        logger = ls.get_logger()
        # Still exactly two handlers
        assert len(logger.handlers) == 2
    finally:
        _cleanup_logger()


def test_setup_logging_json_formatter_selected(
    monkeypatch: pytest.MonkeyPatch, tmp_log_dir: Path
) -> None:
    monkeypatch.setattr(ls, "get_log_dir", lambda: tmp_log_dir)
    # force JSON format branch
    monkeypatch.setattr(ls, "get_log_max_bytes", lambda: 1024)
    monkeypatch.setattr(ls, "get_log_backup_count", lambda: 1)
    monkeypatch.setattr(ls, "get_log_format", lambda: "json")
    monkeypatch.setattr(
        ls, "get_settings", lambda: type("S", (), {"is_verbose_mode": True})()
    )  # verbose: logger level DEBUG

    try:
        handlers = ls.setup_logging(reset=True, return_handlers=True)
        assert handlers is not None

        # Both handlers should use the JSONFormatter
        from agentic_scraper.backend.core.logger_helpers import JSONFormatter

        for h in handlers:
            assert isinstance(h.formatter, JSONFormatter)
    finally:
        _cleanup_logger()

def test_file_handler_rotation_config_respected(
    monkeypatch: pytest.MonkeyPatch, tmp_log_dir: Path
) -> None:
    # Avoid building real Settings when the EnvironmentFilter runs
    monkeypatch.setattr(
        "agentic_scraper.backend.core.logger_helpers.get_environment",
        lambda: "TEST",
    )

    monkeypatch.setattr(ls, "get_log_dir", lambda: tmp_log_dir)
    monkeypatch.setattr(ls, "get_log_format", lambda: "plain")

    # Pin rotation settings to known values and check they are applied
    monkeypatch.setattr(ls, "get_log_max_bytes", lambda: 123456)
    monkeypatch.setattr(ls, "get_log_backup_count", lambda: 7)

    # Non-verbose path for variety
    monkeypatch.setattr(
        ls, "get_settings", lambda: type("S", (), {"is_verbose_mode": False})()
    )
    monkeypatch.setattr(ls, "get_log_level", lambda: logging.WARNING)

    try:
        handlers = ls.setup_logging(reset=True, return_handlers=True)
        assert handlers is not None

        file_handlers = [h for h in handlers if h.__class__.__name__ == "RotatingFileHandler"]
        assert len(file_handlers) == 1
        fh = file_handlers[0]

        # maxBytes and backupCount live on the handler as attributes
        assert getattr(fh, "maxBytes") == 123456
        assert getattr(fh, "backupCount") == 7

        # file exists after a first write (the handler path is created)
        logger = ls.get_logger()
        logger.warning("hello")
        for h in logger.handlers:
            h.flush()
        log_path = tmp_log_dir / "agentic_scraper.log"
        assert log_path.exists()
        assert log_path.stat().st_size >= 0
    finally:
        _cleanup_logger()


def test_teardown_logger_removes_handlers(
    monkeypatch: pytest.MonkeyPatch, tmp_log_dir: Path
) -> None:
    monkeypatch.setattr(ls, "get_log_dir", lambda: tmp_log_dir)
    monkeypatch.setattr(ls, "get_log_format", lambda: "plain")
    monkeypatch.setattr(ls, "get_log_max_bytes", lambda: 1024)
    monkeypatch.setattr(ls, "get_log_backup_count", lambda: 1)    
    monkeypatch.setattr(
        ls, "get_settings", lambda: type("S", (), {"is_verbose_mode": False})()
    )
    monkeypatch.setattr(ls, "get_log_level", lambda: logging.INFO)

    try:
        _ = ls.setup_logging(reset=True, return_handlers=True)
        logger = ls.get_logger()
        assert len(logger.handlers) == 2

        ls.teardown_logger()
        assert logger.handlers == []
    finally:
        _cleanup_logger()
