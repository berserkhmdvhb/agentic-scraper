from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import streamlit as st

from agentic_scraper.backend.config.messages import MSG_UI_RESET_COMPLETE
from agentic_scraper.backend.config.types import AgentMode, OpenAIModel
from agentic_scraper.frontend import app as app_mod
from agentic_scraper.frontend.models import SidebarConfig

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def _make_sidebar_config_llm() -> SidebarConfig:
    # Valid enums so pydantic validation passes
    return SidebarConfig(
        screenshot_enabled=False,
        fetch_concurrency=5,
        llm_concurrency=3,
        verbose=True,
        openai_model=OpenAIModel("gpt-4o"),
        agent_mode=AgentMode.LLM_DYNAMIC,
        retry_attempts=1,
        llm_schema_retries=0,
    )


def test_main_llm_mode_not_logged_in_flow(monkeypatch: MonkeyPatch) -> None:
    """
    Smoke test for main(): LLM mode, not logged in.
    Verifies auth nudges, renderer wiring, and reset hook.
    """
    st.session_state.clear()
    marks: list[str] = []
    calls = {
        "load_settings": 0,
        "auth": 0,
        "render_tabs": 0,
        "run_renderer_called": 0,
        "jobs_renderer_called": 0,
        "reset_app_state": 0,
    }

    # --- Basic scaffolding patches ---
    monkeypatch.setattr(
        app_mod, "setup_logging_and_logger", lambda: logging.getLogger("x"), raising=True
    )

    class _Settings:
        pass

    def _load_settings() -> _Settings:
        calls["load_settings"] += 1
        return _Settings()

    monkeypatch.setattr(app_mod, "load_settings", _load_settings, raising=True)

    def _authenticate_user() -> None:
        calls["auth"] += 1

    monkeypatch.setattr(app_mod, "authenticate_user", _authenticate_user, raising=True)

    # Return LLM config and a non-empty raw_input
    cfg = _make_sidebar_config_llm()
    monkeypatch.setattr(app_mod, "configure_app_page", lambda _s: (cfg, "http://x"), raising=True)

    # Capture top-level info nudges
    def _info(msg: str) -> None:
        marks.append(msg)

    monkeypatch.setattr(st, "info", _info, raising=True)

    # --- Renderers & tab wiring ---
    def _make_render_run(
        *,
        input_ready: str,
        can_run: bool,
        raw_input: str,
        controls: SidebarConfig,
        logger: logging.Logger,
    ) -> Callable[[], None]:
        _ = logger  # silence unused
        assert input_ready.strip() != ""
        assert raw_input.strip() != ""
        # Not logged in → can_run should be False for LLM mode
        assert can_run is False
        assert controls.agent_mode == AgentMode.LLM_DYNAMIC

        def _run_renderer() -> None:
            calls["run_renderer_called"] += 1

        return _run_renderer

    def _make_render_jobs() -> Callable[[str | None], None]:
        def _jobs_renderer(_pre: str | None = None) -> None:
            calls["jobs_renderer_called"] += 1

        return _jobs_renderer

    monkeypatch.setattr(app_mod, "make_render_run", _make_render_run, raising=True)
    monkeypatch.setattr(app_mod, "make_render_jobs", _make_render_jobs, raising=True)

    def _render_main_tabs(
        run_renderer: Callable[[], None],
        jobs_renderer: Callable[[str | None], None],
    ) -> None:
        _ = jobs_renderer  # we simulate Run tab selected
        calls["render_tabs"] += 1
        run_renderer()

    monkeypatch.setattr(app_mod, "render_main_tabs", _render_main_tabs, raising=True)

    def _reset_app_state(_logger: logging.Logger) -> None:
        calls["reset_app_state"] += 1

    monkeypatch.setattr(app_mod, "reset_app_state", _reset_app_state, raising=True)

    # --- Execute ---
    app_mod.main()

    # --- Assertions ---
    assert calls["load_settings"] == 1
    assert calls["auth"] == 1
    assert calls["render_tabs"] == 1
    assert calls["run_renderer_called"] == 1
    assert calls["jobs_renderer_called"] == 0
    assert calls["reset_app_state"] == 1
    # LLM mode + not logged in → top-level info nudge
    assert any("Please log in" in m for m in marks)


def test_main_shows_reset_toast(monkeypatch: MonkeyPatch) -> None:
    """If flash_reset_success is set, main() should toast and clear the flag."""
    st.session_state.clear()
    st.session_state["flash_reset_success"] = True
    toasts: list[str] = []

    # Minimal patches to get through main()
    monkeypatch.setattr(
        app_mod, "setup_logging_and_logger", lambda: logging.getLogger("x"), raising=True
    )
    monkeypatch.setattr(app_mod, "authenticate_user", lambda: None, raising=True)

    class _Settings:
        pass

    monkeypatch.setattr(app_mod, "load_settings", lambda: _Settings(), raising=True)

    cfg = _make_sidebar_config_llm()
    monkeypatch.setattr(app_mod, "configure_app_page", lambda _s: (cfg, "http://x"), raising=True)
    monkeypatch.setattr(app_mod, "render_main_tabs", lambda *_a, **_k: None, raising=True)
    monkeypatch.setattr(app_mod, "reset_app_state", lambda _l: None, raising=True)

    def _toast(msg: str) -> None:
        toasts.append(msg)

    monkeypatch.setattr(st, "toast", _toast, raising=True)

    app_mod.main()

    assert MSG_UI_RESET_COMPLETE in toasts
    assert st.session_state.get("flash_reset_success", False) is False
