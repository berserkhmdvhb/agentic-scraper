from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, TimeoutException

from agentic_scraper.backend.api import lifecycle as lifecycle_mod
from agentic_scraper.backend.api.auth import auth0_helpers as ah
from agentic_scraper.backend.api.lifecycle import lifespan as app_lifespan
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_PRELOADING_JWKS,
    MSG_INFO_JWKS_PRELOAD_SUCCESSFUL,
    MSG_INFO_PRELOADING_JWKS,
    MSG_INFO_SHUTDOWN_LOG,
    MSG_WARNING_JWKS_PRELOAD_FAILED_STARTING_LAZILY,
)

if TYPE_CHECKING:
    # Only for type hints; avoids runtime import (fixes TC002)
    from _pytest.monkeypatch import MonkeyPatch


def _make_app() -> FastAPI:
    app = FastAPI(lifespan=app_lifespan)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "pong"}

    return app


def _spy_logger(monkeypatch: MonkeyPatch) -> list[str]:
    """Monkeypatch lifecycle_mod.logger to capture messages emitted via info/warning/exception."""
    messages: list[str] = []

    def rec(msg: object, *_: object, **__: object) -> None:
        messages.append(str(msg))

    monkeypatch.setattr(lifecycle_mod.logger, "info", rec, raising=True)
    monkeypatch.setattr(lifecycle_mod.logger, "warning", rec, raising=True)
    monkeypatch.setattr(lifecycle_mod.logger, "exception", rec, raising=True)
    return messages


@pytest.mark.asyncio
async def test_lifespan_preloads_jwks_success_logs_info(
    monkeypatch: MonkeyPatch,
) -> None:
    async def _ok() -> list[dict[str, str]]:
        return []

    messages = _spy_logger(monkeypatch)
    monkeypatch.setattr(ah.jwks_cache_instance, "get_jwks", _ok, raising=True)

    app = _make_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.get("/ping")
        assert resp.status_code == status.HTTP_200_OK

    # Assert messages
    assert MSG_INFO_PRELOADING_JWKS in messages
    assert MSG_INFO_JWKS_PRELOAD_SUCCESSFUL in messages
    assert MSG_INFO_SHUTDOWN_LOG in messages


@pytest.mark.asyncio
async def test_lifespan_preload_timeout_logs_warning(
    monkeypatch: MonkeyPatch,
) -> None:
    async def _timeout() -> list[dict[str, str]]:
        msg = "slow"
        raise TimeoutException(msg)

    messages = _spy_logger(monkeypatch)
    monkeypatch.setattr(ah.jwks_cache_instance, "get_jwks", _timeout, raising=True)

    app = _make_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.get("/ping")
        assert resp.status_code == status.HTTP_200_OK

    assert MSG_INFO_PRELOADING_JWKS in messages
    assert MSG_ERROR_PRELOADING_JWKS in messages
    assert MSG_WARNING_JWKS_PRELOAD_FAILED_STARTING_LAZILY in messages
    assert MSG_INFO_SHUTDOWN_LOG in messages


@pytest.mark.asyncio
async def test_lifespan_preload_http_error_logs_warning(
    monkeypatch: MonkeyPatch,
) -> None:
    async def _http_error() -> list[dict[str, str]]:
        msg = "boom"
        raise httpx.HTTPError(msg)

    messages = _spy_logger(monkeypatch)
    monkeypatch.setattr(ah.jwks_cache_instance, "get_jwks", _http_error, raising=True)

    app = _make_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.get("/ping")
        assert resp.status_code == status.HTTP_200_OK

    assert MSG_INFO_PRELOADING_JWKS in messages
    assert MSG_ERROR_PRELOADING_JWKS in messages
    assert MSG_WARNING_JWKS_PRELOAD_FAILED_STARTING_LAZILY in messages
    assert MSG_INFO_SHUTDOWN_LOG in messages


@pytest.mark.asyncio
async def test_lifespan_preload_unexpected_error_logs_warning(
    monkeypatch: MonkeyPatch,
) -> None:
    async def _boom() -> list[dict[str, str]]:
        msg = "kaboom"
        raise RuntimeError(msg)

    messages = _spy_logger(monkeypatch)
    monkeypatch.setattr(ah.jwks_cache_instance, "get_jwks", _boom, raising=True)

    app = _make_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.get("/ping")
        assert resp.status_code == status.HTTP_200_OK

    assert MSG_INFO_PRELOADING_JWKS in messages
    assert MSG_ERROR_PRELOADING_JWKS in messages
    assert MSG_WARNING_JWKS_PRELOAD_FAILED_STARTING_LAZILY in messages
    assert MSG_INFO_SHUTDOWN_LOG in messages


@pytest.mark.asyncio
async def test_shutdown_clears_cancel_events(
    monkeypatch: MonkeyPatch,
) -> None:
    called: dict[str, bool] = {"cleared": False}

    def _clear_all() -> None:
        called["cleared"] = True

    messages = _spy_logger(monkeypatch)

    async def _ok() -> list[dict[str, str]]:
        return []

    monkeypatch.setattr(ah.jwks_cache_instance, "get_jwks", _ok, raising=True)
    monkeypatch.setattr(lifecycle_mod, "clear_cancel_events", _clear_all, raising=True)

    app = _make_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.get("/ping")
        assert resp.status_code == status.HTTP_200_OK

    assert called["cleared"] is True
    assert MSG_INFO_SHUTDOWN_LOG in messages
