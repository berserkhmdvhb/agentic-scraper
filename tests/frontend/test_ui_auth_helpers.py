from __future__ import annotations

import httpx
import pytest
import streamlit as st
from fastapi import status

from agentic_scraper.frontend import ui_auth_helpers as uah


class _DummyQueryParams:
    def __init__(self, token: str | None) -> None:
        self._token = token
        self.cleared = False

    def get(self, _key: str) -> str | None:
        return self._token

    def clear(self) -> None:
        self.cleared = True


def _set_jwt(parts: tuple[str, str, str] | None = None) -> str:
    """Helper to set a JWT in session_state without hardcoded literals."""
    if parts is None:
        parts = ("t", "p", "s")
    token = f"{parts[0]}.{parts[1]}.{parts[2]}"
    st.session_state["jwt_token"] = token
    return token


# ------------------------------- get_jwt_token -------------------------------


def test_get_jwt_token_from_url_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    st.session_state.clear()
    h, p, s = "a", "b", "c"
    expected = f"{h}.{p}.{s}"  # 3 parts -> valid shape
    qp = _DummyQueryParams(expected)
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_auth_helpers.st.query_params",
        qp,
        raising=True,
    )

    tok = uah.get_jwt_token_from_url_or_session()
    assert tok == expected
    assert st.session_state["jwt_token"] == expected
    assert st.session_state.get("auth_pending") is True
    assert qp.cleared is True


def test_get_jwt_token_from_url_malformed_warns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    st.session_state.clear()

    warns: list[str] = []

    def _warn(msg: str) -> None:
        warns.append(msg)

    qp = _DummyQueryParams("abc")  # not header.payload.signature
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_auth_helpers.st.query_params",
        qp,
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_auth_helpers.st.warning",
        _warn,
        raising=True,
    )

    tok = uah.get_jwt_token_from_url_or_session()
    assert tok is None
    assert warns, "expected a warning for malformed token"
    assert qp.cleared is True


def test_get_jwt_token_from_session_fallback() -> None:
    st.session_state.clear()
    token = _set_jwt(("tkn", "part", "end"))
    tok = uah.get_jwt_token_from_url_or_session()
    assert tok == token


# ----------------------------- build_auth_headers ----------------------------


def test_build_auth_headers_requires_jwt() -> None:
    st.session_state.clear()
    with pytest.raises(RuntimeError):
        _ = uah.build_auth_headers()
    h, p, s = "abc", "def", "ghi"
    token = f"{h}.{p}.{s}"
    st.session_state["jwt_token"] = token
    assert uah.build_auth_headers() == {"Authorization": f"Bearer {token}"}


# ------------------------------ fetch_user_profile ---------------------------


def test_fetch_user_profile_success(monkeypatch: pytest.MonkeyPatch) -> None:
    st.session_state.clear()
    _set_jwt(("t", "p", "s"))

    def _get(url: str, headers: dict[str, str], timeout: int) -> httpx.Response:
        _ = headers
        _ = timeout
        req = httpx.Request("GET", url)
        return httpx.Response(status.HTTP_200_OK, request=req, json={"user": "me"})

    monkeypatch.setattr("agentic_scraper.frontend.ui_auth_helpers.httpx.get", _get)

    uah.fetch_user_profile()
    assert st.session_state.get("user_info") == {"user": "me"}


def test_fetch_user_profile_401_triggers_on_unauthorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    st.session_state.clear()
    _set_jwt(("t", "p", "s"))
    calls = {"n": 0}

    def _get(url: str, headers: dict[str, str], timeout: int) -> httpx.Response:
        _ = headers
        _ = timeout
        req = httpx.Request("GET", url)
        return httpx.Response(status.HTTP_401_UNAUTHORIZED, request=req, text="nope")

    def _on_un() -> None:
        calls["n"] += 1

    monkeypatch.setattr("agentic_scraper.frontend.ui_auth_helpers.httpx.get", _get)

    uah.fetch_user_profile(on_unauthorized=_on_un)
    assert calls["n"] == 1


# --------------------------- fetch_openai_credentials -------------------------


def test_fetch_openai_credentials_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    st.session_state.clear()
    _set_jwt(("t", "p", "s"))

    payload = {"api_key": "sk-***masked***", "project_id": "p1"}

    def _get(url: str, headers: dict[str, str], timeout: int) -> httpx.Response:
        _ = headers
        _ = timeout
        req = httpx.Request("GET", url)
        return httpx.Response(status.HTTP_200_OK, request=req, json=payload)

    monkeypatch.setattr("agentic_scraper.frontend.ui_auth_helpers.httpx.get", _get)

    uah.fetch_openai_credentials()
    preview = st.session_state.get("openai_credentials_preview")
    # Comes back as OpenAIConfig; just check fields exist
    assert getattr(preview, "api_key", None) == payload["api_key"]
    assert getattr(preview, "project_id", None) == payload["project_id"]


# ---------------------- fetch_openai_credentials_status ----------------------

def test_fetch_openai_credentials_status_happy(monkeypatch: pytest.MonkeyPatch) -> None:
    st.session_state.clear()
    _set_jwt()

    def _get_ok(url: str, headers: dict[str, str], timeout: int) -> httpx.Response:
        _ = headers
        _ = timeout
        req = httpx.Request("GET", url)
        return httpx.Response(status.HTTP_200_OK, request=req, json={"has_credentials": True})

    monkeypatch.setattr("agentic_scraper.frontend.ui_auth_helpers.httpx.get", _get_ok)
    out = uah.fetch_openai_credentials_status()
    assert out == {"has_credentials": True}


def test_fetch_openai_credentials_status_401_triggers_on_unauthorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    st.session_state.clear()
    _set_jwt()
    calls = {"n": 0}

    def _get_401(url: str, headers: dict[str, str], timeout: int) -> httpx.Response:
        _ = headers
        _ = timeout
        req = httpx.Request("GET", url)
        return httpx.Response(status.HTTP_401_UNAUTHORIZED, request=req, text="nope")

    def _on_un() -> None:
        calls["n"] += 1

    monkeypatch.setattr("agentic_scraper.frontend.ui_auth_helpers.httpx.get", _get_401)
    out = uah.fetch_openai_credentials_status(on_unauthorized=_on_un)
    assert out is None
    assert calls["n"] == 1


def test_fetch_openai_credentials_status_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    st.session_state.clear()
    _set_jwt()
    errs: list[str] = []

    def _err(msg: str) -> None:
        errs.append(msg)

    def _get_bad_json(url: str, headers: dict[str, str], timeout: int) -> httpx.Response:
        _ = headers
        _ = timeout
        req = httpx.Request("GET", url)
        return httpx.Response(status.HTTP_200_OK, request=req, text="{not:json}")

    monkeypatch.setattr("agentic_scraper.frontend.ui_auth_helpers.httpx.get", _get_bad_json)
    monkeypatch.setattr("agentic_scraper.frontend.ui_auth_helpers.st.error", _err, raising=True)
    out = uah.fetch_openai_credentials_status()
    assert out == {"has_credentials": False}


def test_fetch_openai_credentials_status_http_500(monkeypatch: pytest.MonkeyPatch) -> None:
    st.session_state.clear()
    _set_jwt()
    errs: list[str] = []

    def _err(msg: str) -> None:
        errs.append(msg)

    def _get_500(url: str, headers: dict[str, str], timeout: int) -> httpx.Response:
        _ = headers
        _ = timeout
        req = httpx.Request("GET", url)
        return httpx.Response(status.HTTP_500_INTERNAL_SERVER_ERROR, request=req, text="boom")

    monkeypatch.setattr("agentic_scraper.frontend.ui_auth_helpers.httpx.get", _get_500)
    monkeypatch.setattr("agentic_scraper.frontend.ui_auth_helpers.st.error", _err, raising=True)
    out = uah.fetch_openai_credentials_status()
    assert out is None
    assert errs


def test_fetch_openai_credentials_status_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    st.session_state.clear()
    _set_jwt()
    errs: list[str] = []

    def _err(msg: str) -> None:
        errs.append(msg)

    def _get_raise(url: str, headers: dict[str, str], timeout: int) -> httpx.Response:
        _ = headers
        _ = timeout
        msg = "oops"
        req = httpx.Request("GET", url)
        raise httpx.RequestError(msg, request=req)

    monkeypatch.setattr("agentic_scraper.frontend.ui_auth_helpers.httpx.get", _get_raise)
    monkeypatch.setattr("agentic_scraper.frontend.ui_auth_helpers.st.error", _err, raising=True)
    out = uah.fetch_openai_credentials_status()
    assert out is None
    assert errs
