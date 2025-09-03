from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import streamlit as st
from typing_extensions import Self

from agentic_scraper.backend.config.messages import (
    MSG_UI_LOGGED_OUT_APP_ONLY,
    MSG_UI_LOGGING_IN,
)
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.frontend import ui_auth as ua

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def _set_jwt(parts: tuple[str, str, str] = ("hdr", "pay", "sig")) -> str:
    token = ".".join(parts)
    st.session_state["jwt_token"] = token
    return token


class _SidebarDummy:
    """A minimal Streamlit sidebar stand-in with context manager support."""

    def __init__(self) -> None:
        self.infos: list[str] = []
        self.markdowns: list[str] = []
        self.captions: list[str] = []
        self.buttons: list[tuple[str, bool]] = []  # (label, disabled)
        self.link_buttons: list[tuple[str, str]] = []  # (label, url)
        self._next_button_value: bool = False  # controls next button() return

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        return None

    def info(self, msg: str) -> None:
        self.infos.append(msg)

    def markdown(self, msg: str, *, unsafe_allow_html: bool | None = None) -> None:
        _ = unsafe_allow_html  # keep ruff happy
        self.markdowns.append(msg)

    def caption(self, msg: str) -> None:
        self.captions.append(msg)

    def button(
        self,
        label: str,
        *,
        use_container_width: bool | None = None,
        disabled: bool | None = None,
    ) -> bool:
        _ = use_container_width
        self.buttons.append((label, bool(disabled)))
        val = self._next_button_value
        self._next_button_value = False
        return val

    def link_button(
        self,
        label: str,
        url: str,
        *,
        help_text: str | None = None,
    ) -> None:
        _ = help_text
        self.link_buttons.append((label, url))

    # Helpers to control button return value from tests
    def set_next_button_click(self, *, value: bool) -> None:
        self._next_button_value = value


# ------------------------- authenticate_user -------------------------


def test_authenticate_user_early_return(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    _set_jwt()
    st.session_state["user_info"] = {"name": "Alice"}

    called = {"profile": 0, "status": 0, "fetch": 0, "rerun": 0}

    def _profile(*, on_unauthorized: Callable[[], None] | None = None) -> None:
        _ = on_unauthorized  # avoid unused-arg lint
        called["profile"] += 1

    def _status(*, on_unauthorized: Callable[[], None] | None = None) -> dict[str, bool] | None:
        _ = on_unauthorized  # silence unused-arg
        called["status"] += 1
        return {"has_credentials": True}

    def _fetch(*, on_unauthorized: Callable[[], None] | None = None) -> None:
        _ = on_unauthorized
        called["fetch"] += 1

    def _rerun() -> None:
        called["rerun"] += 1

    monkeypatch.setattr(ua, "fetch_user_profile", _profile, raising=True)
    monkeypatch.setattr(ua, "fetch_openai_credentials_status", _status, raising=True)
    monkeypatch.setattr(ua, "fetch_openai_credentials", _fetch, raising=True)
    monkeypatch.setattr(st, "rerun", _rerun, raising=True)

    ua.authenticate_user()
    assert called == {"profile": 0, "status": 0, "fetch": 0, "rerun": 0}


def test_authenticate_user_fetches_creds_when_status_true(
    monkeypatch: MonkeyPatch,
) -> None:
    st.session_state.clear()

    def _get_jwt() -> str | None:
        return _set_jwt()

    called = {"profile": 0, "status": 0, "fetch": 0, "rerun": 0}

    def _profile(*, on_unauthorized: Callable[[], None] | None = None) -> None:
        _ = on_unauthorized  # avoid unused-arg lint
        called["profile"] += 1

    def _status(*, on_unauthorized: Callable[[], None] | None = None) -> dict[str, bool] | None:
        _ = on_unauthorized  # silence unused-arg
        called["status"] += 1
        return {"has_credentials": True}

    def _fetch(*, on_unauthorized: Callable[[], None] | None = None) -> None:
        _ = on_unauthorized
        called["fetch"] += 1

    def _rerun() -> None:
        called["rerun"] += 1

    monkeypatch.setattr(ua, "get_jwt_token_from_url_or_session", _get_jwt, raising=True)
    monkeypatch.setattr(ua, "fetch_user_profile", _profile, raising=True)
    monkeypatch.setattr(ua, "fetch_openai_credentials_status", _status, raising=True)
    monkeypatch.setattr(ua, "fetch_openai_credentials", _fetch, raising=True)
    monkeypatch.setattr(st, "rerun", _rerun, raising=True)

    ua.authenticate_user()

    assert called["profile"] == 1
    assert called["status"] == 1
    assert called["fetch"] == 1
    assert called["rerun"] == 1
    assert st.session_state.get("has_openai_credentials") is True
    assert st.session_state.get("auth_pending") is False


def test_authenticate_user_status_false_skips_fetch(
    monkeypatch: MonkeyPatch,
) -> None:
    st.session_state.clear()

    def _get_jwt() -> str | None:
        return _set_jwt()

    # include profile (and optionally status) to match increments below
    called = {"fetch": 0, "rerun": 0, "profile": 0}

    def _profile(*, on_unauthorized: Callable[[], None] | None = None) -> None:
        _ = on_unauthorized
        called["profile"] += 1

    def _status(*, on_unauthorized: Callable[[], None] | None = None) -> dict[str, bool] | None:
        _ = on_unauthorized
        return {"has_credentials": False}

    def _fetch(*, on_unauthorized: Callable[[], None] | None = None) -> None:
        _ = on_unauthorized
        called["fetch"] += 1

    def _rerun() -> None:
        called["rerun"] += 1

    monkeypatch.setattr(ua, "get_jwt_token_from_url_or_session", _get_jwt, raising=True)
    monkeypatch.setattr(ua, "fetch_user_profile", _profile, raising=True)
    monkeypatch.setattr(ua, "fetch_openai_credentials_status", _status, raising=True)
    monkeypatch.setattr(ua, "fetch_openai_credentials", _fetch, raising=True)
    monkeypatch.setattr(st, "rerun", _rerun, raising=True)

    ua.authenticate_user()

    assert called["fetch"] == 0
    assert called["rerun"] == 1
    assert st.session_state.get("has_openai_credentials") is False
    assert st.session_state.get("auth_pending") is False


def test_authenticate_user_unauthorized_calls_logout(
    monkeypatch: MonkeyPatch,
) -> None:
    st.session_state.clear()

    def _get_jwt() -> str | None:
        return _set_jwt()

    called = {"logout": 0, "rerun": 0, "profile": 0}

    def _profile(*, on_unauthorized: Callable[[], None] | None = None) -> None:
        _ = on_unauthorized
        called["profile"] += 1

    # Simulate the 401 path by invoking the callback here
    def _status(*, on_unauthorized: Callable[[], None] | None = None) -> dict[str, bool] | None:
        if on_unauthorized is not None:
            on_unauthorized()
        return None

    def _logout() -> None:
        called["logout"] += 1

    def _rerun() -> None:
        called["rerun"] += 1

    monkeypatch.setattr(ua, "get_jwt_token_from_url_or_session", _get_jwt, raising=True)
    monkeypatch.setattr(ua, "fetch_user_profile", _profile, raising=True)
    monkeypatch.setattr(ua, "fetch_openai_credentials_status", _status, raising=True)
    monkeypatch.setattr(ua, "logout_user", _logout, raising=True)
    monkeypatch.setattr(st, "rerun", _rerun, raising=True)

    ua.authenticate_user()

    assert called["logout"] == 1
    assert called["rerun"] == 1


# ------------------------- logout_user -------------------------


def test_logout_user_clears_session_and_sets_banner(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    st.session_state.update(
        {
            "jwt_token": "h.p.s",
            "user_info": {"name": "A"},
            "openai_credentials": {"x": 1},
            "openai_credentials_preview": {"y": 2},
            "auth_pending": True,
            "has_openai_credentials": True,
        }
    )
    called = {"rerun": 0}

    def _rerun() -> None:
        called["rerun"] += 1

    monkeypatch.setattr(st, "rerun", _rerun, raising=True)

    ua.logout_user()

    assert "jwt_token" not in st.session_state
    assert "user_info" not in st.session_state
    assert "openai_credentials" not in st.session_state
    assert "openai_credentials_preview" not in st.session_state
    assert "auth_pending" not in st.session_state
    assert "has_openai_credentials" not in st.session_state
    assert st.session_state.get("show_logged_out_banner") is True
    assert called["rerun"] == 1


# ------------------------- login_ui (sidebar) -------------------------


def test_login_ui_rule_based_returns_early(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    side = _SidebarDummy()
    monkeypatch.setattr(st, "sidebar", side, raising=True)

    # Should render nothing / not use sidebar for rule-based
    ua.login_ui(AgentMode.RULE_BASED)
    assert side.infos == []
    assert side.buttons == []
    assert side.markdowns == []
    assert side.captions == []


def test_login_ui_pending_shows_logging_in(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    st.session_state["auth_pending"] = True
    side = _SidebarDummy()

    # Mount the sidebar dummy and route UI calls into it
    monkeypatch.setattr(st, "sidebar", side, raising=True)
    monkeypatch.setattr(st, "info", side.info, raising=True)
    monkeypatch.setattr(st, "markdown", side.markdown, raising=True)
    monkeypatch.setattr(st, "caption", side.caption, raising=True)
    monkeypatch.setattr(st, "button", side.button, raising=True)

    ua.login_ui(AgentMode.LLM_DYNAMIC_ADAPTIVE)

    # Should show "logging in" message and return — no buttons/captions
    assert MSG_UI_LOGGING_IN in side.infos
    assert len(side.buttons) == 0
    assert len(side.captions) == 0


def test_login_ui_render_login_buttons_when_not_pending(
    monkeypatch: MonkeyPatch,
) -> None:
    st.session_state.clear()
    side = _SidebarDummy()

    # Stubs that accept the same signature as production helpers
    def _login_url(*, scope_list: list[str] | None = None) -> str:
        _ = scope_list
        return "https://auth/login"

    def _force_url(*, scope_list: list[str] | None = None) -> str:
        _ = scope_list
        return "https://auth/force"

    # Mount the sidebar dummy and route UI calls into it
    monkeypatch.setattr(st, "sidebar", side, raising=True)
    monkeypatch.setattr(st, "info", side.info, raising=True)
    monkeypatch.setattr(st, "markdown", side.markdown, raising=True)
    monkeypatch.setattr(st, "caption", side.caption, raising=True)
    monkeypatch.setattr(st, "button", side.button, raising=True)

    monkeypatch.setattr(ua, "build_login_url", _login_url, raising=True)
    monkeypatch.setattr(ua, "build_force_login_url", _force_url, raising=True)

    ua.login_ui(AgentMode.LLM_DYNAMIC_ADAPTIVE)

    # A normal (enabled) login button is rendered
    assert len(side.buttons) >= 1
    assert side.buttons[-1][1] is False
    # A caption with the force-auth link should also be present
    assert len(side.captions) >= 1
    assert "Force re-authentication" in side.captions[-1]


def test_login_ui_clicking_login_enters_pending_and_meta_refresh(
    monkeypatch: MonkeyPatch,
) -> None:
    st.session_state.clear()
    side = _SidebarDummy()
    side.set_next_button_click(value=True)  # simulate user clicking the login button

    def _login_url(*, scope_list: list[str] | None = None) -> str:
        _ = scope_list
        return "https://auth/login"

    def _force_url(*, scope_list: list[str] | None = None) -> str:
        _ = scope_list
        return "https://auth/force"

    # Capture stop() to avoid halting test
    stopped = {"n": 0}

    def _stop() -> None:
        stopped["n"] += 1

    # Mount the sidebar dummy and route UI calls into it
    monkeypatch.setattr(st, "sidebar", side, raising=True)
    monkeypatch.setattr(st, "info", side.info, raising=True)
    monkeypatch.setattr(st, "markdown", side.markdown, raising=True)
    monkeypatch.setattr(st, "caption", side.caption, raising=True)
    monkeypatch.setattr(st, "button", side.button, raising=True)
    monkeypatch.setattr(st, "stop", _stop, raising=True)

    monkeypatch.setattr(ua, "build_login_url", _login_url, raising=True)
    monkeypatch.setattr(ua, "build_force_login_url", _force_url, raising=True)

    ua.login_ui(AgentMode.LLM_DYNAMIC_ADAPTIVE)

    # Pending should be set, logging message shown, meta refresh injected, and stop called
    assert st.session_state.get("auth_pending") is True
    assert MSG_UI_LOGGING_IN in side.infos
    assert any('http-equiv="refresh"' in m for m in side.markdowns)
    assert stopped["n"] == 1


def test_login_ui_logged_in_shows_user_and_logout_controls(
    monkeypatch: MonkeyPatch,
) -> None:
    st.session_state.clear()
    _set_jwt()
    st.session_state["user_info"] = {"name": "Dana", "email": "d@example.com"}
    side = _SidebarDummy()

    def _logout_url() -> str:
        return "https://auth/logout"

    # Ensure the "Logout (this app)" button is not clicked
    side.set_next_button_click(value=False)

    # Route Streamlit calls into the sidebar dummy
    monkeypatch.setattr(st, "sidebar", side, raising=True)
    monkeypatch.setattr(st, "markdown", side.markdown, raising=True)
    monkeypatch.setattr(st, "button", side.button, raising=True)

    # Adapter to map Streamlit's kwarg name to the dummy's
    def _link_button(label: str, url: str, **kwargs: object) -> None:
        help_val = kwargs.get("help")
        side.link_button(
            label,
            url,
            help_text=help_val if isinstance(help_val, str) else None,
        )

    monkeypatch.setattr(st, "link_button", _link_button, raising=True)
    monkeypatch.setattr(ua, "build_logout_url", _logout_url, raising=True)

    ua.login_ui(AgentMode.LLM_DYNAMIC_ADAPTIVE)

    # Name and email are rendered in markdown (simple smoke checks)
    assert any("Welcome" in m for m in side.markdowns)
    assert any("Email" in m for m in side.markdowns)

    # A federated logout link is shown
    assert len(side.link_buttons) >= 1
    assert side.link_buttons[-1][1] == "https://auth/logout"


def test_logout_user_banner_message_is_shown_next_time(monkeypatch: MonkeyPatch) -> None:
    # After logout, user returns to the app not logged in, banner should appear once
    st.session_state.clear()
    ua.logout_user()  # sets show_logged_out_banner=True and reruns

    def _rerun() -> None:
        return None

    side = _SidebarDummy()
    monkeypatch.setattr(st, "sidebar", side, raising=True)
    monkeypatch.setattr(st, "rerun", _rerun, raising=True)
    monkeypatch.setattr(st, "info", side.info, raising=True)

    ua.login_ui(AgentMode.LLM_DYNAMIC_ADAPTIVE)
    assert MSG_UI_LOGGED_OUT_APP_ONLY in side.infos

    # On second render, the banner flag is consumed
    side2 = _SidebarDummy()
    monkeypatch.setattr(st, "sidebar", side2, raising=True)
    monkeypatch.setattr(st, "info", side2.info, raising=True)
    ua.login_ui(AgentMode.LLM_DYNAMIC_ADAPTIVE)
    assert MSG_UI_LOGGED_OUT_APP_ONLY not in side2.infos
