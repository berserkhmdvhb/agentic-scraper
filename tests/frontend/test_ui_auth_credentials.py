from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import httpx
import streamlit as st
from fastapi import status
from typing_extensions import Self

from agentic_scraper.frontend import ui_auth_credentials as uac

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

# ---------------------------------------------------------------------------
# Module-level constants (avoid magic numbers)
# ---------------------------------------------------------------------------

# Button call indices (1-based) inside render_credentials_actions
BUTTON_IDX_UPDATE = 1
BUTTON_IDX_DELETE = 2
BUTTON_IDX_CONFIRM = 3
BUTTON_IDX_CANCEL = 4

# Number of columns used in the credentials actions UI
NUM_COLUMNS = 2

# ---------------------------------------------------------------------------
# Common monkeypatch target strings (avoid long lines)
# ---------------------------------------------------------------------------

PUT_PATH = "agentic_scraper.frontend.ui_auth_credentials.httpx.put"
DEL_PATH = "agentic_scraper.frontend.ui_auth_credentials.httpx.delete"
ST_SUCCESS = "agentic_scraper.frontend.ui_auth_credentials.st.success"
ST_ERROR = "agentic_scraper.frontend.ui_auth_credentials.st.error"
ST_MD = "agentic_scraper.frontend.ui_auth_credentials.st.markdown"
ST_WRITE = "agentic_scraper.frontend.ui_auth_credentials.st.write"
ST_COLUMNS = "agentic_scraper.frontend.ui_auth_credentials.st.columns"
ST_FORM = "agentic_scraper.frontend.ui_auth_credentials.st.form"
ST_TEXT_INPUT = "agentic_scraper.frontend.ui_auth_credentials.st.text_input"
ST_FORM_SUBMIT = "agentic_scraper.frontend.ui_auth_credentials.st.form_submit_button"
ST_EXPANDER = "agentic_scraper.frontend.ui_auth_credentials.st.expander"
ST_BUTTON = "agentic_scraper.frontend.ui_auth_credentials.st.button"
ST_RERUN = "agentic_scraper.frontend.ui_auth_credentials.st.rerun"
FETCH_PREVIEW = "agentic_scraper.frontend.ui_auth_credentials.fetch_openai_credentials"
FETCH_STATUS = "agentic_scraper.frontend.ui_auth_credentials.fetch_openai_credentials_status"
ACTIONS_PATH = "agentic_scraper.frontend.ui_auth_credentials.render_credentials_actions"

# ----------------------------- put_openai_credentials -----------------------------


def test_put_openai_credentials_requires_login(
    monkeypatch: MonkeyPatch,
    st_session: Callable[[dict[str, Any] | None], None],
) -> None:
    st_session({})
    errs: list[str] = []

    def _err(msg: str) -> None:
        errs.append(msg)

    # Capture error UI via monkeypatch
    monkeypatch.setattr(ST_ERROR, _err, raising=True)

    ok = uac.put_openai_credentials("sk-abc", "proj-1")
    assert ok is False
    assert any("logged in" in m for m in errs)


def test_put_openai_credentials_success_sets_session_and_fetches_preview(
    monkeypatch: MonkeyPatch,
    st_session: Callable[[dict[str, Any] | None], None],
) -> None:
    st_session({"jwt_token": "h.p.s"})

    called = {"fetch_preview": 0, "success": 0}

    def _put(
        url: str,
        *,
        json: dict[str, str],
        headers: dict[str, str],
        timeout: int,
    ) -> httpx.Response:
        _ = timeout
        # basic sanity on request fields
        assert "api" in json["api_key"]
        assert headers.get("Authorization") == f"Bearer {st.session_state['jwt_token']}"
        req = httpx.Request("PUT", url)
        return httpx.Response(status.HTTP_200_OK, request=req, json={"ok": True})

    def _fetch_preview() -> None:
        called["fetch_preview"] += 1
        # simulate backend-masked preview being populated by helper
        st.session_state["openai_credentials_preview"] = {
            "api_key": "sk-***masked***",
            "project_id": "p1",
        }

    def _success(msg: str) -> None:
        called["success"] += 1
        assert "saved successfully" in msg.lower()

    monkeypatch.setattr(PUT_PATH, _put, raising=True)
    monkeypatch.setattr(FETCH_PREVIEW, _fetch_preview, raising=True)
    monkeypatch.setattr(ST_SUCCESS, _success, raising=True)

    ok = uac.put_openai_credentials("api-key", "p1")
    assert ok is True
    # real (unmasked) creds stored as OpenAIConfig
    cfg = st.session_state.get("openai_credentials")
    assert getattr(cfg, "api_key", None) == "api-key"
    assert getattr(cfg, "project_id", None) == "p1"
    # masked preview fetched
    assert called["fetch_preview"] == 1
    assert called["success"] == 1


def test_put_openai_credentials_http_error_shows_message(
    monkeypatch: MonkeyPatch,
    st_session: Callable[[dict[str, Any] | None], None],
) -> None:
    st_session({"jwt_token": "h.p.s"})
    errs: list[str] = []

    def _put(
        url: str,
        *,
        json: dict[str, str],
        headers: dict[str, str],
        timeout: int,
    ) -> httpx.Response:
        _ = json, headers, timeout
        req = httpx.Request("PUT", url)
        # 400 so raise_for_status will raise HTTPStatusError in the function
        return httpx.Response(status.HTTP_400_BAD_REQUEST, request=req, text="bad")

    def _err(msg: str) -> None:
        errs.append(msg)

    monkeypatch.setattr(PUT_PATH, _put, raising=True)
    monkeypatch.setattr(ST_ERROR, _err, raising=True)

    ok = uac.put_openai_credentials("api", "p1")
    assert ok is False
    assert errs  # message shown


def test_put_openai_credentials_network_error(
    monkeypatch: MonkeyPatch,
    st_session: Callable[[dict[str, Any] | None], None],
) -> None:
    st_session({"jwt_token": "h.p.s"})
    errs: list[str] = []

    def _put(
        url: str,
        *,
        json: dict[str, str],
        headers: dict[str, str],
        timeout: int,
    ) -> httpx.Response:
        _ = json, headers, timeout
        req = httpx.Request("PUT", url)
        msg = "boom"
        raise httpx.RequestError(msg, request=req)

    def _err(msg: str) -> None:
        errs.append(msg)

    monkeypatch.setattr(PUT_PATH, _put, raising=True)
    monkeypatch.setattr(ST_ERROR, _err, raising=True)

    ok = uac.put_openai_credentials("api", "p1")
    assert ok is False
    assert any("network error" in m.lower() for m in errs)


# ----------------------------- delete_openai_credentials -----------------------------


def test_delete_openai_credentials_requires_login(
    monkeypatch: MonkeyPatch,
    st_session: Callable[[dict[str, Any] | None], None],
) -> None:
    st_session({})
    msgs: list[str] = []

    def _err(msg: str) -> None:
        msgs.append(msg)

    monkeypatch.setattr(ST_ERROR, _err, raising=True)

    ok = uac.delete_openai_credentials()
    assert ok is False
    assert any("logged in" in m for m in msgs)


def test_delete_openai_credentials_success(
    monkeypatch: MonkeyPatch,
    st_session: Callable[[dict[str, Any] | None], None],
) -> None:
    st_session({"jwt_token": "h.p.s", "has_openai_credentials": True})

    def _delete(
        url: str,
        *,
        headers: dict[str, str],
        timeout: int,
    ) -> httpx.Response:
        _ = headers, timeout
        req = httpx.Request("DELETE", url)
        return httpx.Response(status.HTTP_200_OK, request=req, json={"ok": True})

    monkeypatch.setattr(DEL_PATH, _delete, raising=True)

    ok = uac.delete_openai_credentials()
    assert ok is True
    assert st.session_state.get("has_openai_credentials") is False


def test_delete_openai_credentials_http_error(
    monkeypatch: MonkeyPatch,
    st_session: Callable[[dict[str, Any] | None], None],
) -> None:
    st_session({"jwt_token": "h.p.s"})
    errs: list[str] = []

    def _delete(
        url: str,
        *,
        headers: dict[str, str],
        timeout: int,
    ) -> httpx.Response:
        _ = headers, timeout
        req = httpx.Request("DELETE", url)
        return httpx.Response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            request=req,
            text="boom",
        )

    def _err(msg: str) -> None:
        errs.append(msg)

    monkeypatch.setattr(DEL_PATH, _delete, raising=True)
    monkeypatch.setattr(ST_ERROR, _err, raising=True)

    ok = uac.delete_openai_credentials()
    assert ok is False
    assert errs


def test_delete_openai_credentials_network_error(
    monkeypatch: MonkeyPatch,
    st_session: Callable[[dict[str, Any] | None], None],
) -> None:
    st_session({"jwt_token": "h.p.s"})
    errs: list[str] = []

    def _delete(
        url: str,
        *,
        headers: dict[str, str],
        timeout: int,
    ) -> httpx.Response:
        _ = headers, timeout
        req = httpx.Request("DELETE", url)
        msg = "nope"
        raise httpx.RequestError(msg, request=req)

    def _err(msg: str) -> None:
        errs.append(msg)

    monkeypatch.setattr(DEL_PATH, _delete, raising=True)
    monkeypatch.setattr(ST_ERROR, _err, raising=True)

    ok = uac.delete_openai_credentials()
    assert ok is False
    assert any("network error" in m.lower() for m in errs)


# -------- render_credentials_form (preview) --------


def test_render_credentials_form_shows_preview_when_has_creds_true(
    monkeypatch: MonkeyPatch,
    st_session: Callable[[dict[str, Any] | None], None],
) -> None:
    # Seed: user already has credentials + masked preview
    st_session(
        {
            "has_openai_credentials": True,
            "openai_credentials_preview": {
                "api_key": "sk-***masked***",
                "project_id": "p123",
            },
        }
    )

    lines: list[str] = []
    called = {"actions": 0}

    def _md(msg: str) -> None:
        lines.append(msg)

    def _write(msg: str) -> None:
        # We will collect project id / api key lines
        lines.append(str(msg))

    def _success(_msg: str) -> None:
        return None

    def _actions() -> None:
        called["actions"] += 1

    monkeypatch.setattr(ST_MD, _md, raising=True)
    monkeypatch.setattr(ST_WRITE, _write, raising=True)
    monkeypatch.setattr(ST_SUCCESS, _success, raising=True)
    monkeypatch.setattr(ACTIONS_PATH, _actions, raising=True)

    uac.render_credentials_form()

    # Preview content printed
    assert any("Project ID" in s for s in lines)
    assert any("API Key" in s for s in lines)
    # Actions rendered
    assert called["actions"] == 1


def test_render_credentials_form_initializes_status_when_missing_false(
    monkeypatch: MonkeyPatch,
    st_session: Callable[[dict[str, Any] | None], None],
) -> None:
    # No flag in session; status says no credentials
    st_session({})

    def _status() -> dict[str, bool] | None:
        return {"has_credentials": False}

    # ensure the flag is written without real network/form behavior
    monkeypatch.setattr(FETCH_STATUS, _status, raising=True)

    def _md(_msg: str) -> None:
        return None

    monkeypatch.setattr(ST_MD, _md, raising=True)

    # Minimal stubs so the function can proceed without error.
    class _FormDummy:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object, **kwargs: object) -> None:
            return None

    def _form(_key: str) -> _FormDummy:
        return _FormDummy()

    def _text_input(*_args: object, **_kwargs: object) -> str:
        return ""  # empty to avoid submission

    def _submit(_label: str) -> bool:
        return False

    monkeypatch.setattr(ST_FORM, _form, raising=True)
    monkeypatch.setattr(ST_TEXT_INPUT, _text_input, raising=True)
    monkeypatch.setattr(ST_FORM_SUBMIT, _submit, raising=True)

    uac.render_credentials_form()
    # Flag should be initialized to False
    assert st.session_state.get("has_openai_credentials") is False


# ----------------------------- render_credentials_actions -----------------------------


def test_render_credentials_actions_update_triggers_rerun(
    monkeypatch: MonkeyPatch,
    st_session: Callable[[dict[str, Any] | None], None],
) -> None:
    st_session(
        {
            "openai_credentials": object(),
            "openai_credentials_preview": {"api_key": "sk-***", "project_id": "p"},
        }
    )
    calls = {"rerun": 0}

    # st.columns(2) returns two column-like objects with button() method
    class _Col:
        def __init__(self, *, value: bool) -> None:
            self._seq = [value]

        # support `with col:` used by the implementation
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def button(self, _label: str) -> bool:
            return self._seq.pop(0) if self._seq else False

    # First column: Update clicked → True; second: Delete not clicked → False
    cols = (_Col(value=True), _Col(value=False))

    def _columns(n: int) -> tuple[_Col, _Col]:
        assert n == NUM_COLUMNS
        return cols

    def _rerun() -> None:
        calls["rerun"] += 1

    monkeypatch.setattr(ST_COLUMNS, _columns, raising=True)
    monkeypatch.setattr(ST_RERUN, _rerun, raising=True)

    # First st.button() call (Update) should return True; others False
    btn_calls = {"n": 0}

    def _button(_label: str) -> bool:
        btn_calls["n"] += 1
        return btn_calls["n"] == BUTTON_IDX_UPDATE

    monkeypatch.setattr(ST_BUTTON, _button, raising=True)

    uac.render_credentials_actions()
    # Update clicked → credentials removed and rerun requested
    assert "openai_credentials" not in st.session_state
    assert st.session_state.get("openai_credentials_preview") is None
    assert calls["rerun"] == 1


def test_render_credentials_actions_click_delete_sets_confirm_flag(
    monkeypatch: MonkeyPatch,
    st_session: Callable[[dict[str, Any] | None], None],
) -> None:
    st_session({"has_openai_credentials": True})

    class _Col:
        def __init__(self) -> None:
            return None

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object, **_kwargs: object) -> None:
            return None

    def _columns(_n: int) -> tuple[_Col, _Col]:
        # two columns used only as context managers
        return (_Col(), _Col())

    monkeypatch.setattr(ST_COLUMNS, _columns, raising=True)

    # First st.button() (Update) -> False; second (Delete) -> True
    btn_calls = {"n": 0}

    def _button(_label: str) -> bool:
        btn_calls["n"] += 1
        return btn_calls["n"] == BUTTON_IDX_DELETE

    monkeypatch.setattr(ST_BUTTON, _button, raising=True)

    # Clicking the top-level "Delete" sets the confirm flag
    uac.render_credentials_actions()
    assert st.session_state.get("confirm_delete") is True


def test_render_credentials_actions_confirm_delete_executes_and_reruns(
    monkeypatch: MonkeyPatch,
    st_session: Callable[[dict[str, Any] | None], None],
) -> None:
    # Enter the expander branch directly
    st_session({"has_openai_credentials": True, "confirm_delete": True})

    class _Exp:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object, **__: object) -> None:
            return None

    class _Col:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object, **__: object) -> None:
            return None

    # Simple, branch-free stubs
    monkeypatch.setattr(ST_EXPANDER, lambda _label: _Exp(), raising=True)
    monkeypatch.setattr(ST_COLUMNS, lambda _n: (_Col(), _Col()), raising=True)

    # Button order: Update, Delete, Confirm, Cancel -> only Confirm=True
    btn_iter = iter([False, False, True, False])
    monkeypatch.setattr(ST_BUTTON, lambda _label: next(btn_iter, False), raising=True)

    # Backend delete succeeds
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_auth_credentials.delete_openai_credentials",
        lambda: True,
        raising=True,
    )

    calls = {"success": 0, "rerun": 0}
    monkeypatch.setattr(
        ST_SUCCESS, lambda _msg: calls.__setitem__("success", calls["success"] + 1), raising=True
    )
    monkeypatch.setattr(
        ST_RERUN, lambda: calls.__setitem__("rerun", calls["rerun"] + 1), raising=True
    )

    uac.render_credentials_actions()

    assert st.session_state.get("has_openai_credentials") is False
    assert "confirm_delete" not in st.session_state
    assert calls["success"] == 1
    assert calls["rerun"] == 1
