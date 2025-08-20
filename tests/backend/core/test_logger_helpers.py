import logging
from logging import LogRecord

import pytest
from _pytest.monkeypatch import MonkeyPatch

from agentic_scraper.backend.core.logger_helpers import (
    EnvironmentFilter,
    JSONFormatter,
    SafeFormatter,
)


def test_environment_filter_sets_env(monkeypatch: MonkeyPatch) -> None:
    # Force a specific environment
    monkeypatch.setattr(
        "agentic_scraper.backend.core.logger_helpers.get_environment",
        lambda: "TESTENV",
    )
    f = EnvironmentFilter()
    rec: LogRecord = logging.LogRecord("x", logging.INFO, __file__, 10, "msg", (), None)
    assert f.filter(rec) is True
    assert getattr(rec, "env") == "TESTENV"


def test_safe_formatter_injects_env_when_missing() -> None:
    fmt = SafeFormatter(fmt="[%(env)s] %(levelname)s %(message)s")
    # LogRecord with no env attribute
    rec: LogRecord = logging.LogRecord("x", logging.INFO, __file__, 10, "hello", (), None)
    out = fmt.format(rec)
    assert out.startswith("[UNKNOWN] ")

    # If env exists, it’s preserved
    rec2: LogRecord = logging.LogRecord("x", logging.WARNING, __file__, 10, "bye", (), None)
    setattr(rec2, "env", "DEV")
    out2 = fmt.format(rec2)
    assert out2.startswith("[DEV] ")


def test_json_formatter_structure_and_time(monkeypatch: MonkeyPatch) -> None:
    jf = JSONFormatter()
    # Monkeypatch formatTime directly for deterministic output
    monkeypatch.setattr(
        JSONFormatter,
        "formatTime",
        lambda self, record, datefmt=None: "2020-01-02T03:04:05",
    )

    rec: LogRecord = logging.LogRecord("my.logger", logging.ERROR, __file__, 20, "boom", (), None)
    # simulate env injected by filter
    setattr(rec, "env", "PROD")

    out = jf.format(rec)
    assert '"timestamp": "2020-01-02T03:04:05"' in out
    assert '"level": "ERROR"' in out
    assert '"env": "PROD"' in out
    assert '"logger": "my.logger"' in out
    assert '"message": "boom"' in out

    # With extra fields
    rec2: LogRecord = logging.LogRecord("my.logger", logging.INFO, __file__, 10, "ok", (), None)
    setattr(rec2, "env", "DEV")
    setattr(rec2, "extra", {"job_id": "J123", "stage": "fetch"})
    out2 = jf.format(rec2)
    assert '"job_id": "J123"' in out2
    assert '"stage": "fetch"' in out2


def test_json_formatter_includes_traceback() -> None:
    jf = JSONFormatter()
    try:
        raise RuntimeError("kaboom")
    except RuntimeError as e:
        # Build a LogRecord with a properly-typed exc_info tuple
        rec: LogRecord = logging.LogRecord(
            "x",
            logging.ERROR,
            __file__,
            10,
            "err",
            (),
            (RuntimeError, e, e.__traceback__),
        )
        setattr(rec, "env", "DEV")
        out = jf.format(rec)
        assert '"traceback":' in out
