from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx
import pytest
from fastapi import status
from typing_extensions import Self


class DummyResp:
    def __init__(
        self,
        status_code: int,
        json_data: dict[str, Any] | None = None,
        text: str = "",
        content_type: str = "application/json",
    ) -> None:
        self.status_code = status_code
        self._data = json_data
        self.text = text
        self.headers: dict[str, str] = {}
        if json_data is not None and content_type:
            self.headers["content-type"] = content_type

    def json(self) -> dict[str, Any]:
        if self._data is None:
            msg = "No JSON available"
            raise ValueError(msg)
        return self._data


class DummyClient:
    """Async context manager that returns a canned response to `.post()`."""

    def __init__(self, resp: DummyResp) -> None:
        self._resp = resp

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        return None

    async def post(self, *_args: object, **_kwargs: object) -> DummyResp:
        return self._resp


class ExplodingClient:
    """Raises an exception when used, to exercise error path."""

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        return None

    async def post(self, *_args: object, **_kwargs: object) -> DummyResp:
        err = RuntimeError("boom")
        raise err


@pytest.mark.asyncio
async def test_auth_callback_missing_code_redirects_error(
    test_client: httpx.AsyncClient,
    api_base: str,
) -> None:
    res = await test_client.get(f"{api_base}/auth/callback")
    assert res.status_code in {
        status.HTTP_302_FOUND,
        status.HTTP_307_TEMPORARY_REDIRECT,
    }
    assert "error=missing_code" in (res.headers.get("location") or "")


@pytest.mark.asyncio
async def test_auth_callback_success_token_redirects_with_token(
    monkeypatch: pytest.MonkeyPatch,
    test_client: httpx.AsyncClient,
    api_base: str,
) -> None:
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_kw: DummyClient(DummyResp(200, {"access_token": "tok_123"})),
        raising=True,
    )

    res = await test_client.get(f"{api_base}/auth/callback?code=abc123")
    assert res.status_code in {
        status.HTTP_302_FOUND,
        status.HTTP_307_TEMPORARY_REDIRECT,
    }
    loc = res.headers.get("location") or ""
    assert "token=tok_123" in loc


@pytest.mark.asyncio
async def test_auth_callback_non_200_yields_token_exchange_failed(
    monkeypatch: pytest.MonkeyPatch,
    test_client: httpx.AsyncClient,
    api_base: str,
) -> None:
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_kw: DummyClient(DummyResp(400, text="error body")),
        raising=True,
    )

    res = await test_client.get(f"{api_base}/auth/callback?code=abc123")
    assert res.status_code in {
        status.HTTP_302_FOUND,
        status.HTTP_307_TEMPORARY_REDIRECT,
    }
    assert "error=token_exchange_failed" in (res.headers.get("location") or "")


@pytest.mark.asyncio
async def test_auth_callback_200_missing_token_yields_missing_token(
    monkeypatch: pytest.MonkeyPatch,
    test_client: httpx.AsyncClient,
    api_base: str,
) -> None:
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_kw: DummyClient(DummyResp(200, {})),
        raising=True,
    )

    res = await test_client.get(f"{api_base}/auth/callback?code=abc123")
    assert res.status_code in {
        status.HTTP_302_FOUND,
        status.HTTP_307_TEMPORARY_REDIRECT,
    }
    assert "error=missing_token" in (res.headers.get("location") or "")


@pytest.mark.asyncio
async def test_auth_callback_exception_path_yields_token_exchange_failed(
    monkeypatch: pytest.MonkeyPatch,
    test_client: httpx.AsyncClient,
    api_base: str,
) -> None:
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_kw: ExplodingClient(),
        raising=True,
    )

    res = await test_client.get(f"{api_base}/auth/callback?code=abc123")
    assert res.status_code in {
        status.HTTP_302_FOUND,
        status.HTTP_307_TEMPORARY_REDIRECT,
    }
    assert "error=token_exchange_failed" in (res.headers.get("location") or "")
