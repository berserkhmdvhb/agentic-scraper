from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import httpx
import streamlit as st
from fastapi import status

from agentic_scraper.frontend import ui_jobs as uj

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OK_LIMIT = 20
TIMEOUT_S = 30

PATH_GET = "agentic_scraper.frontend.ui_jobs._get_cached"
PATH_DELETE = "agentic_scraper.frontend.ui_jobs._delete"
PATH_FILTERS = "agentic_scraper.frontend.ui_jobs._render_filters"
PATH_CURSOR = "agentic_scraper.frontend.ui_jobs._init_and_get_cursor"
PATH_LIST = "agentic_scraper.frontend.ui_jobs.fetch_jobs"
PATH_TOOLBAR = "agentic_scraper.frontend.ui_jobs._render_pagination_toolbar"
PATH_TABLE = "agentic_scraper.frontend.ui_jobs._render_jobs_table"
PATH_SELECT = "agentic_scraper.frontend.ui_jobs._select_job"
PATH_HANDLE = "agentic_scraper.frontend.ui_jobs._handle_selected_job"
PATH_AUTO_LIST = "agentic_scraper.frontend.ui_jobs._maybe_list_autorefresh"

# Safe token parts to avoid S105 warning (not a single hardcoded secret)
DUMMY_JWT = "dummy.jwt.token"

# ---------------------------------------------------------------------------
# fetch_jobs
# ---------------------------------------------------------------------------


def test_fetch_jobs_happy_path_builds_items_and_cursor(
    monkeypatch: MonkeyPatch, st_session: Callable[[dict[str, Any] | None], None]
) -> None:
    st_session({"jwt_token": DUMMY_JWT})

    def _get(url: str, jwt: str, *, timeout: int = TIMEOUT_S) -> httpx.Response:
        _ = timeout  # consume
        assert "status_=running" in url
        assert "limit=20" in url
        assert "cursor=abc" in url
        assert jwt == DUMMY_JWT
        req = httpx.Request("GET", url)
        data = {"items": [{"id": "1"}, {"id": "2"}], "next_cursor": "zzz"}
        return httpx.Response(status.HTTP_200_OK, request=req, json=data)

    monkeypatch.setattr(PATH_GET, _get, raising=True)

    items, nxt = uj.fetch_jobs("running", OK_LIMIT, "abc")
    assert [i["id"] for i in items] == ["1", "2"]
    assert nxt == "zzz"


def test_fetch_jobs_401_clears_jwt_and_informs(
    monkeypatch: MonkeyPatch, st_session: Callable[[dict[str, Any] | None], None]
) -> None:
    st_session({"jwt_token": DUMMY_JWT})
    infos: list[str] = []
    monkeypatch.setattr(st, "info", lambda m: infos.append(m), raising=True)

    def _get(url: str, jwt: str, *, timeout: int = TIMEOUT_S) -> httpx.Response:
        _ = jwt, timeout
        req = httpx.Request("GET", url)
        return httpx.Response(status.HTTP_401_UNAUTHORIZED, request=req, text="unauth")

    monkeypatch.setattr(PATH_GET, _get, raising=True)

    items, nxt = uj.fetch_jobs(None, OK_LIMIT, None)
    assert items == []
    assert nxt is None
    assert "jwt_token" not in st.session_state
    assert infos


def test_fetch_jobs_http_and_network_errors_show_errors(
    monkeypatch: MonkeyPatch, st_session: Callable[[dict[str, Any] | None], None]
) -> None:
    st_session({"jwt_token": DUMMY_JWT})
    errs: list[str] = []
    monkeypatch.setattr(st, "error", lambda m: errs.append(m), raising=True)

    # HTTP 500
    def _get_500(url: str, jwt: str, *, timeout: int = TIMEOUT_S) -> httpx.Response:
        _ = jwt, timeout
        req = httpx.Request("GET", url)
        return httpx.Response(status.HTTP_500_INTERNAL_SERVER_ERROR, request=req, text="boom")

    monkeypatch.setattr(PATH_GET, _get_500, raising=True)
    items, nxt = uj.fetch_jobs("all", OK_LIMIT, None)
    assert items == []
    assert nxt is None
    assert errs

    # Network error
    errs.clear()

    def _get_raise(url: str, jwt: str, *, timeout: int = TIMEOUT_S) -> httpx.Response:
        _ = jwt, timeout
        req = httpx.Request("GET", url)
        msg = "oops"
        raise httpx.RequestError(msg, request=req)

    monkeypatch.setattr(PATH_GET, _get_raise, raising=True)
    items, nxt = uj.fetch_jobs("queued", OK_LIMIT, None)
    assert items == []
    assert nxt is None
    assert errs


# ---------------------------------------------------------------------------
# fetch_job
# ---------------------------------------------------------------------------


def test_fetch_job_success_and_selective_statuses(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    warns: list[str] = []
    errs: list[str] = []
    infos: list[str] = []
    monkeypatch.setattr(st, "warning", lambda m: warns.append(m), raising=True)
    monkeypatch.setattr(st, "error", lambda m: errs.append(m), raising=True)
    monkeypatch.setattr(st, "info", lambda m: infos.append(m), raising=True)

    # 200 OK -> payload dict returned
    def _get_ok(url: str, jwt: str, *, timeout: int = TIMEOUT_S) -> httpx.Response:
        _ = jwt, timeout
        req = httpx.Request("GET", url)
        return httpx.Response(status.HTTP_200_OK, request=req, json={"id": "j1"})

    monkeypatch.setattr(PATH_GET, _get_ok, raising=True)
    out = uj.fetch_job("j1")
    assert out == {"id": "j1"}

    # 404 -> warning, None
    def _get_404(url: str, jwt: str, *, timeout: int = TIMEOUT_S) -> httpx.Response:
        _ = jwt, timeout
        req = httpx.Request("GET", url)
        return httpx.Response(status.HTTP_404_NOT_FOUND, request=req, text="nope")

    monkeypatch.setattr(PATH_GET, _get_404, raising=True)
    out2 = uj.fetch_job("j2")
    assert out2 is None
    assert warns

    # 403 -> error, None
    warns.clear()

    def _get_403(url: str, jwt: str, *, timeout: int = TIMEOUT_S) -> httpx.Response:
        _ = jwt, timeout
        req = httpx.Request("GET", url)
        return httpx.Response(status.HTTP_403_FORBIDDEN, request=req, text="forbid")

    monkeypatch.setattr(PATH_GET, _get_403, raising=True)
    out3 = uj.fetch_job("j3")
    assert out3 is None
    assert errs

    # 401 -> clears jwt, info
    errs.clear()
    st.session_state["jwt_token"] = DUMMY_JWT

    def _get_401(url: str, jwt: str, *, timeout: int = TIMEOUT_S) -> httpx.Response:
        _ = jwt, timeout
        req = httpx.Request("GET", url)
        return httpx.Response(status.HTTP_401_UNAUTHORIZED, request=req, text="unauth")

    monkeypatch.setattr(PATH_GET, _get_401, raising=True)
    out4 = uj.fetch_job("j4")
    assert out4 is None
    assert "jwt_token" not in st.session_state
    assert infos


def test_fetch_job_exceptions_show_messages(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    errs: list[str] = []
    monkeypatch.setattr(st, "error", lambda m: errs.append(m), raising=True)

    # HTTPStatusError path: simulate a non-handled 4xx/5xx + raise_for_status()
    def _get_418(_url: str, _jwt: str, *, timeout: int = TIMEOUT_S) -> httpx.Response:
        _ = timeout  # consume
        req = httpx.Request("GET", _url)
        return httpx.Response(418, request=req, text="teapot")

    # We let fetch_job call raise_for_status(); it will catch HTTPStatusError
    monkeypatch.setattr(PATH_GET, _get_418, raising=True)
    _ = uj.fetch_job("j5")
    assert errs  # message shown

    # RequestError path
    errs.clear()

    def _get_raise(url: str, jwt: str, *, timeout: int = TIMEOUT_S) -> httpx.Response:
        _ = jwt, timeout
        req = httpx.Request("GET", url)
        msg = "down"
        raise httpx.RequestError(msg, request=req)

    monkeypatch.setattr(PATH_GET, _get_raise, raising=True)
    _ = uj.fetch_job("j6")
    assert errs


# ---------------------------------------------------------------------------
# cancel_job
# ---------------------------------------------------------------------------


def test_cancel_job_status_matrix(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    st.session_state["jwt_token"] = DUMMY_JWT
    msgs: dict[str, int] = {"success": 0, "info": 0, "warn": 0, "error": 0}

    def _inc(key: str) -> None:
        msgs[key] = msgs[key] + 1

    def _succ(_m: str) -> None:
        _inc("success")

    def _info(_m: str) -> None:
        _inc("info")

    def _warn(_m: str) -> None:
        _inc("warn")

    def _err(_m: str) -> None:
        _inc("error")

    monkeypatch.setattr(st, "success", _succ, raising=True)
    monkeypatch.setattr(st, "info", _info, raising=True)
    monkeypatch.setattr(st, "warning", _warn, raising=True)
    monkeypatch.setattr(st, "error", _err, raising=True)

    def _del(code: int) -> Callable[[str], httpx.Response]:
        def _inner(url: str, *, timeout: int = TIMEOUT_S) -> httpx.Response:
            _ = timeout
            req = httpx.Request("DELETE", url)
            return httpx.Response(code, request=req, text="x")

        return _inner

    # 204 -> success True
    monkeypatch.setattr(PATH_DELETE, _del(status.HTTP_204_NO_CONTENT), raising=True)
    assert uj.cancel_job("a") is True
    # 409 -> info, False
    monkeypatch.setattr(PATH_DELETE, _del(status.HTTP_409_CONFLICT), raising=True)
    assert uj.cancel_job("b") is False
    # 404 -> warning, False
    monkeypatch.setattr(PATH_DELETE, _del(status.HTTP_404_NOT_FOUND), raising=True)
    assert uj.cancel_job("c") is False
    # 403 -> error, False
    monkeypatch.setattr(PATH_DELETE, _del(status.HTTP_403_FORBIDDEN), raising=True)
    assert uj.cancel_job("d") is False
    # 500 -> error with safe message, False
    monkeypatch.setattr(PATH_DELETE, _del(status.HTTP_500_INTERNAL_SERVER_ERROR), raising=True)
    assert uj.cancel_job("e") is False

    # RequestError path
    def _del_raise(url: str, *, timeout: int = TIMEOUT_S) -> httpx.Response:
        _ = timeout
        req = httpx.Request("DELETE", url)
        msg = "net"
        raise httpx.RequestError(msg, request=req)

    monkeypatch.setattr(PATH_DELETE, _del_raise, raising=True)
    assert uj.cancel_job("f") is False

    # Ensure at least one of each UI call fired
    assert msgs["success"] >= 1
    assert msgs["info"] >= 1
    assert msgs["warn"] >= 1
    assert msgs["error"] >= 1


# ---------------------------------------------------------------------------
# render_jobs_tab: drive via public entrypoint with internal stubs
# ---------------------------------------------------------------------------


def test_render_jobs_tab_lists_and_opens_selected_job(
    monkeypatch: MonkeyPatch, st_session: Callable[[dict[str, Any] | None], None]
) -> None:
    st_session({"jwt_token": DUMMY_JWT})

    # Filters return running/limit/auto=True/manual=False
    monkeypatch.setattr(PATH_FILTERS, lambda: ("running", OK_LIMIT, True, False), raising=True)
    monkeypatch.setattr(PATH_CURSOR, lambda: None, raising=True)

    # fetch_jobs returns items and next_cursor
    items = [
        {"id": "j1", "status": "succeeded"},
        {"id": "j2", "status": "running"},
    ]
    monkeypatch.setattr(PATH_LIST, lambda *_a, **_k: (items, "cur2"), raising=True)

    # No-op UI bits
    monkeypatch.setattr(PATH_TOOLBAR, lambda *_a, **_k: None, raising=True)
    monkeypatch.setattr(PATH_AUTO_LIST, lambda *_a, **_k: None, raising=True)

    # Table returns rows + ids
    monkeypatch.setattr(PATH_TABLE, lambda _items: (_items, ["j1", "j2"]), raising=True)
    # Auto-select j2
    monkeypatch.setattr(PATH_SELECT, lambda _ids, _pre: "j2", raising=True)

    called = {"handle": 0}

    def _handle(sel: str | None, *, auto_refresh: bool, manual_refresh_clicked: bool) -> None:
        assert sel == "j2"
        assert auto_refresh is True
        assert manual_refresh_clicked is False
        called["handle"] += 1

    monkeypatch.setattr(PATH_HANDLE, _handle, raising=True)

    # Minimal display widgets
    monkeypatch.setattr(st, "header", lambda *_a, **_k: None, raising=True)
    monkeypatch.setattr(st, "info", lambda *_a, **_k: None, raising=True)

    uj.render_jobs_tab()
    assert called["handle"] == 1


def test_render_jobs_tab_requires_login_shows_info(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    infos: list[str] = []
    monkeypatch.setattr(st, "header", lambda *_a, **_k: None, raising=True)
    monkeypatch.setattr(st, "info", lambda msg: infos.append(msg), raising=True)

    uj.render_jobs_tab()
    assert infos
