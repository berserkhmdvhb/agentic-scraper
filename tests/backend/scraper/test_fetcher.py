from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, cast

import httpx
import pytest

from agentic_scraper.backend.config.constants import FETCH_ERROR_PREFIX
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.cancel_helpers import CancelToken
from agentic_scraper.backend.scraper.fetcher import fetch_all, fetch_url

TEST_FERNET_KEY = "A" * 43 + "="
EXPECTED_RETRY_ATTEMPTS = 2  # avoid magic number in assertions


def _settings(**overrides: object) -> Settings:
    """
    Real Settings with small timeouts; provide required fields inline so CI
    doesn't depend on environment variables or global fixtures.
    """
    base = Settings.model_validate(
        {
            # Required auth/security (use actual field names)
            "AUTH0_DOMAIN": "test.auth0.com",
            "AUTH0_ISSUER": "https://test.auth0.com/",
            "AUTH0_CLIENT_ID": "client-id",
            "AUTH0_CLIENT_SECRET": "client-secret",
            "ENCRYPTION_SECRET": TEST_FERNET_KEY,
            # Required backend/frontend
            "BACKEND_DOMAIN": "http://api.example.com",
            "AUTH0_API_AUDIENCE": "https://api.example.com",
            "FRONTEND_DOMAIN": "http://app.example.com",
            "AUTH0_REDIRECT_URI": "http://api.example.com/auth/callback",
        }
    )
    # Apply per-test tweaks (don't try to set the is_verbose_mode property)
    return base.model_copy(
        update={
            "request_timeout": 0.05,
            "retry_attempts": 1,
            **overrides,
        }
    )


def _factory_with_transport(transport: httpx.MockTransport) -> Callable[..., httpx.AsyncClient]:
    """
    Return a factory callable compatible with fetch_all(client_factory=...).
    We keep **kwargs typed broadly to cover possible httpx.AsyncClient kwargs.
    """

    def factory(**kwargs: dict[str, Any]) -> httpx.AsyncClient:
        # mypy: AsyncClient(**kwargs) expects precisely-typed kwargs. Since this
        # is a test helper that forwards whatever fetch_all passes through, cast
        # to a permissive mapping.
        kwargs_any = cast("dict[str, Any]", kwargs)
        return httpx.AsyncClient(
            transport=cast("httpx.AsyncBaseTransport", transport),
            **kwargs_any,
        )

    return factory


@pytest.mark.asyncio
async def test_fetch_all_empty_returns_empty() -> None:
    settings = _settings()
    out = await fetch_all([], settings=settings, concurrency=5)
    assert out == {}


@pytest.mark.asyncio
async def test_fetch_all_success_multiple() -> None:
    settings = _settings()
    data = {
        "https://a.test/": "<a/>",
        "https://b.test/": "<b/>",
        "https://c.test/": "<c/>",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        content = data[str(request.url)]
        return httpx.Response(200, text=content, request=request)

    transport = httpx.MockTransport(handler)
    out = await fetch_all(
        list(data.keys()),
        settings=settings,
        concurrency=3,
        client_factory=_factory_with_transport(transport),
    )
    assert out == data


@pytest.mark.asyncio
async def test_fetch_all_records_http_errors() -> None:
    settings = _settings()
    urls = ["https://ok.test/", "https://err.test/"]

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("err.test/"):
            return httpx.Response(500, text="boom", request=request)
        return httpx.Response(200, text="<ok/>", request=request)

    transport = httpx.MockTransport(handler)
    out = await fetch_all(
        urls,
        settings=settings,
        concurrency=2,
        client_factory=_factory_with_transport(transport),
    )

    assert out["https://ok.test/"] == "<ok/>"
    assert out["https://err.test/"].startswith(FETCH_ERROR_PREFIX)


@pytest.mark.asyncio
async def test_fetch_url_retry_then_success() -> None:
    # First attempt -> timeout, second attempt -> 200 OK
    settings = _settings(request_timeout=0.01, retry_attempts=EXPECTED_RETRY_ATTEMPTS)

    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            # Simulate timeout on first call by raising from transport
            msg = "timeout"
            raise httpx.ReadTimeout(msg, request=request)
        return httpx.Response(200, text="<ok-after-retry/>", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        html = await fetch_url(
            client,
            "https://retry.test/",
            settings=settings,
            cancel_event=None,
            should_cancel=None,
        )
    assert html == "<ok-after-retry/>"
    assert attempts["n"] == EXPECTED_RETRY_ATTEMPTS


@pytest.mark.asyncio
async def test_fetch_url_cancel_raises_cancelled() -> None:
    settings = _settings()
    cancel_event = asyncio.Event()
    cancel_event.set()

    transport = httpx.MockTransport(lambda req: httpx.Response(200, text="<never/>", request=req))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(asyncio.CancelledError):
            await fetch_url(
                client,
                "https://cancel.test/",
                settings=settings,
                cancel_event=cancel_event,
            )


@pytest.mark.asyncio
async def test_fetch_all_honors_cancel_and_marks_entries() -> None:
    settings = _settings()
    cancel_event = asyncio.Event()
    cancel_event.set()  # cancel before starting

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<unused/>", request=request)

    transport = httpx.MockTransport(handler)
    out = await fetch_all(
        ["https://x.test/"],
        settings=settings,
        concurrency=1,
        cancel=CancelToken(event=cancel_event),
        client_factory=_factory_with_transport(transport),
    )

    assert out["https://x.test/"].startswith(FETCH_ERROR_PREFIX)
    assert "canceled" in out["https://x.test/"]


@pytest.mark.asyncio
async def test_fetch_all_concurrency_nonpositive_is_clamped() -> None:
    """If a caller passes 0/negative, we still fetch using a minimum of 1."""
    settings = _settings()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<ok/>", request=request)

    transport = httpx.MockTransport(handler)
    out = await fetch_all(
        ["https://t.test/1", "https://t.test/2"],
        settings=settings,
        concurrency=0,
        client_factory=_factory_with_transport(transport),
    )
    assert out == {
        "https://t.test/1": "<ok/>",
        "https://t.test/2": "<ok/>",
    }
