# tests/backend/api/utils/test_log_helpers.py
from __future__ import annotations

import logging

import pytest
from fastapi import HTTPException
from jose import JWTError

from agentic_scraper.backend.api.utils import log_helpers as lh
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_INTERNAL_SERVER,
    MSG_ERROR_INVALID_TOKEN,
    MSG_ERROR_MISSING_SCOPES,
    MSG_INFO_USER_AUTHORIZED,
    MSG_WARNING_INSUFFICIENT_PERMISSIONS,
    MSG_WARNING_USER_FAILED_AUTHORIZATION,
)

STATUS_FORBIDDEN = 403
STATUS_UNAUTHORIZED = 401
STATUS_INTERNAL_ERROR = 500


def _find_log(caplog: pytest.LogCaptureFixture, level: int, substring: str) -> bool:
    return any((rec.levelno == level) and (substring in rec.getMessage()) for rec in caplog.records)


def test_raise_forbidden_logs_and_raises(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    required = ["read:user_profile", "write:stuff"]

    with pytest.raises(HTTPException) as ei:
        lh.raise_forbidden(required)

    exc = ei.value
    assert exc.status_code == STATUS_FORBIDDEN
    scopes_str = " ".join(required)
    assert exc.detail == MSG_ERROR_MISSING_SCOPES.format(scopes=scopes_str)
    assert exc.headers == {"WWW-Authenticate": "Bearer"}

    # warning log contains formatted scopes
    assert _find_log(caplog, logging.WARNING, MSG_WARNING_INSUFFICIENT_PERMISSIONS.split("{")[0])
    assert _find_log(caplog, logging.WARNING, scopes_str)


def test_raise_unauthorized_logs_and_raises(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    err = JWTError("boom-why")

    with pytest.raises(HTTPException) as ei:
        lh.raise_unauthorized(err)

    exc = ei.value
    assert exc.status_code == STATUS_UNAUTHORIZED
    # detail is hardcoded in implementation (recommend moving to constants)
    assert exc.detail == "Invalid or expired token"
    assert exc.headers == {"WWW-Authenticate": "Bearer"}

    # An exception-level log with formatted error text (logger.exception → ERROR level)
    expect_prefix = MSG_ERROR_INVALID_TOKEN.split("{")[0]
    assert _find_log(caplog, logging.ERROR, expect_prefix)
    assert _find_log(caplog, logging.ERROR, "boom-why")


def test_raise_internal_error_logs_and_raises(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    err = RuntimeError("oops")

    with pytest.raises(HTTPException) as ei:
        lh.raise_internal_error(err)

    exc = ei.value
    assert exc.status_code == STATUS_INTERNAL_ERROR
    # detail is hardcoded in implementation (recommend moving to constants)
    assert exc.detail == "Internal server error during token validation"
    assert exc.headers == {"WWW-Authenticate": "Bearer"}

    expect_prefix = MSG_ERROR_INTERNAL_SERVER.split("{")[0]
    assert _find_log(caplog, logging.ERROR, expect_prefix)
    assert _find_log(caplog, logging.ERROR, "oops")


def test_log_helpers_info_warning_error(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    lh.log_raise_info("hello-info", user="u1")
    lh.log_raise_warning("hello-warn", user="u2")
    lh.log_raise_error("hello-err", user="u3")

    assert _find_log(caplog, logging.INFO, "hello-info")
    assert _find_log(caplog, logging.WARNING, "hello-warn")
    # log_raise_error uses logger.exception → ERROR level
    assert _find_log(caplog, logging.ERROR, "hello-err")


def test_log_raise_user_authorization(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    lh.log_raise_user_authorization("user-123", success=True)
    lh.log_raise_user_authorization("user-456", success=False)

    ok_prefix = MSG_INFO_USER_AUTHORIZED.split("{")[0]
    bad_prefix = MSG_WARNING_USER_FAILED_AUTHORIZATION.split("{")[0]

    # INFO message: should include the constant text and the user id
    assert _find_log(caplog, logging.INFO, ok_prefix)
    assert _find_log(caplog, logging.INFO, "user-123")

    # WARNING message: should include the constant text and the user id
    assert _find_log(caplog, logging.WARNING, bad_prefix)
    assert _find_log(caplog, logging.WARNING, "user-456")
