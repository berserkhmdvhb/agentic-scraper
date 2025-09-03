from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st
from typing_extensions import Self

from agentic_scraper.backend.config.constants import SESSION_KEYS, URL_NUDGE_THRESHOLD
from agentic_scraper.backend.config.types import AgentMode, OpenAIModel
from agentic_scraper.frontend import ui_sidebar as uis

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

    from agentic_scraper.backend.core import settings as settings_module


# ---------------------------------------------------------------------------
# Constants for deterministic expectations (avoid magic numbers)
# ---------------------------------------------------------------------------

FETCH_CONC_VAL = 7
LLM_CONC_VAL = 3
RETRY_ATTEMPTS_VAL = 2
SCHEMA_RETRIES_VAL = 1

# String targets (to avoid long lines)
PATH_HDR = "agentic_scraper.frontend.ui_sidebar._render_header_chip_row"
PATH_AUTH = "agentic_scraper.frontend.ui_sidebar._render_auth_and_env"
PATH_ADV = "agentic_scraper.frontend.ui_sidebar._render_advanced_settings"
PATH_JOBS = "agentic_scraper.frontend.ui_sidebar._render_jobs_footer"


# ---------------------------------------------------------------------------
# Small helpers / dummies
# ---------------------------------------------------------------------------


class _Ctx:
    """Simple context manager stand-in for Streamlit containers (sidebar, expander)."""

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object, **__: object) -> None:
        return None


def _no_ui(*_args: object, **_kwargs: object) -> None:
    """No-op UI primitive for tests."""


# ---------------------------------------------------------------------------
# render_sidebar_controls (happy path, with internals stubbed by string targets)
# ---------------------------------------------------------------------------


def test_render_sidebar_controls_persists_values_and_returns_config(
    monkeypatch: MonkeyPatch,
    settings: settings_module.Settings,
) -> None:
    st.session_state.clear()

    # Sidebar container + simple primitives
    monkeypatch.setattr(st, "sidebar", _Ctx(), raising=True)
    monkeypatch.setattr(st, "caption", _no_ui, raising=True)
    monkeypatch.setattr(st, "divider", _no_ui, raising=True)

    # Stub private internals via string path (avoids SLF001)
    monkeypatch.setattr(PATH_HDR, _no_ui, raising=True)
    monkeypatch.setattr(PATH_AUTH, _no_ui, raising=True)
    monkeypatch.setattr(PATH_JOBS, _no_ui, raising=True)

    # Drive selections through the *public* flow by controlling widgets
    selected_agent_mode = AgentMode.LLM_DYNAMIC
    selected_model = OpenAIModel(settings.openai_model.value)

    # LLM controls path: model selectbox returns the settings' model key
    model_key = settings.openai_model.value

    def _selectbox_llm(label: str, **_k: object) -> str:
        # differentiate calls: first selectbox used above for agent mode; next for model
        if "OpenAI Model" in label:
            return model_key
        return selected_agent_mode.value

    monkeypatch.setattr(st, "selectbox", _selectbox_llm, raising=True)

    # Screenshot checkbox → True
    monkeypatch.setattr(st, "checkbox", lambda *_a, **_k: True, raising=True)
    monkeypatch.setattr(st, "subheader", _no_ui, raising=True)

    # Advanced settings: stub via string target to return deterministic tuple
    monkeypatch.setattr(
        PATH_ADV,
        lambda *_a, **_k: (
            FETCH_CONC_VAL,
            LLM_CONC_VAL,
            True,
            RETRY_ATTEMPTS_VAL,
            SCHEMA_RETRIES_VAL,
        ),
        raising=True,
    )

    cfg = uis.render_sidebar_controls(settings)

    # Check object returned
    assert cfg.agent_mode == selected_agent_mode
    assert cfg.openai_model == selected_model
    assert cfg.fetch_concurrency == FETCH_CONC_VAL
    assert cfg.llm_concurrency == LLM_CONC_VAL
    assert cfg.verbose is True
    assert cfg.retry_attempts == RETRY_ATTEMPTS_VAL
    assert cfg.llm_schema_retries == SCHEMA_RETRIES_VAL

    # Check session persistence
    assert st.session_state[SESSION_KEYS["agent_mode"]] == selected_agent_mode
    assert st.session_state[SESSION_KEYS["openai_model"]] == selected_model
    assert st.session_state[SESSION_KEYS["fetch_concurrency"]] == FETCH_CONC_VAL
    assert st.session_state[SESSION_KEYS["llm_concurrency"]] == LLM_CONC_VAL
    assert st.session_state[SESSION_KEYS["verbose"]] is True
    assert st.session_state[SESSION_KEYS["retry_attempts"]] == RETRY_ATTEMPTS_VAL
    assert st.session_state[SESSION_KEYS["llm_schema_retries"]] == SCHEMA_RETRIES_VAL


# ---------------------------------------------------------------------------
# LLM controls path exercised through the public render (nudge + persistence)
# ---------------------------------------------------------------------------


def test_llm_controls_nudge_and_checkbox_persistence_via_public_render(
    monkeypatch: MonkeyPatch,
    settings: settings_module.Settings,
) -> None:
    st.session_state.clear()
    st.session_state["url_count"] = URL_NUDGE_THRESHOLD  # trigger nudge if screenshots on

    # Replace only the pieces we don't assert here
    monkeypatch.setattr(PATH_HDR, _no_ui, raising=True)
    monkeypatch.setattr(PATH_AUTH, _no_ui, raising=True)
    monkeypatch.setattr(PATH_ADV, lambda *_a, **_k: (5, 5, False, 1, 1), raising=True)
    monkeypatch.setattr(PATH_JOBS, _no_ui, raising=True)

    # Sidebar container
    monkeypatch.setattr(st, "sidebar", _Ctx(), raising=True)
    monkeypatch.setattr(st, "divider", _no_ui, raising=True)
    monkeypatch.setattr(st, "subheader", _no_ui, raising=True)

    # Agent mode select → non-rule-based
    monkeypatch.setattr(
        st, "selectbox", lambda *_a, **_k: AgentMode.LLM_DYNAMIC.value, raising=True
    )

    # Model selectbox (inside LLM controls) returns a valid key
    model_key = settings.openai_model.value

    def _selectbox_chain(label: str, **_k: object) -> str:
        if "OpenAI Model" in label:
            return model_key
        return AgentMode.LLM_DYNAMIC.value

    monkeypatch.setattr(st, "selectbox", _selectbox_chain, raising=True)

    # Screenshot checkbox returns True to trigger the nudge
    monkeypatch.setattr(st, "checkbox", lambda *_a, **_k: True, raising=True)

    nudges: list[str] = []
    monkeypatch.setattr(st, "caption", lambda msg: nudges.append(msg), raising=True)

    cfg = uis.render_sidebar_controls(settings)
    assert isinstance(cfg.openai_model, OpenAIModel)
    assert cfg.openai_model.value == model_key
    assert st.session_state[SESSION_KEYS["screenshot_enabled"]] is True
    assert any("consider turning screenshots off" in s.lower() for s in nudges)


# ---------------------------------------------------------------------------
# Rule-based path via public render (no model picker; screenshot off)
# ---------------------------------------------------------------------------


def test_rule_based_path_hides_model_and_keeps_default_via_public_render(
    monkeypatch: MonkeyPatch,
    settings: settings_module.Settings,
) -> None:
    st.session_state.clear()

    monkeypatch.setattr(PATH_HDR, _no_ui, raising=True)
    monkeypatch.setattr(PATH_AUTH, _no_ui, raising=True)
    monkeypatch.setattr(
        PATH_ADV,
        lambda *_a, **_k: (6, 0, False, 1, settings.llm_schema_retries),
        raising=True,
    )
    monkeypatch.setattr(PATH_JOBS, _no_ui, raising=True)

    monkeypatch.setattr(st, "sidebar", _Ctx(), raising=True)
    monkeypatch.setattr(st, "divider", _no_ui, raising=True)
    monkeypatch.setattr(st, "subheader", _no_ui, raising=True)

    # Agent mode -> RULE_BASED
    monkeypatch.setattr(st, "selectbox", lambda *_a, **_k: AgentMode.RULE_BASED.value, raising=True)
    # Screenshot checkbox -> False
    monkeypatch.setattr(st, "checkbox", lambda *_a, **_k: False, raising=True)

    cfg = uis.render_sidebar_controls(settings)
    assert cfg.openai_model == settings.openai_model
    assert st.session_state[SESSION_KEYS["screenshot_enabled"]] is False


# ---------------------------------------------------------------------------
# Jobs footer smoke via public render hook (no private calls)
# ---------------------------------------------------------------------------


def test_jobs_footer_content_is_shown_when_last_job_present(
    monkeypatch: MonkeyPatch,
    settings: settings_module.Settings,
) -> None:
    st.session_state.clear()
    st.session_state["last_job_id"] = "job-123"
    st.session_state["last_job_status"] = "succeeded"

    # We run through public render but short-circuit most internals
    monkeypatch.setattr(st, "sidebar", _Ctx(), raising=True)
    monkeypatch.setattr(PATH_HDR, _no_ui, raising=True)
    monkeypatch.setattr(PATH_AUTH, _no_ui, raising=True)
    monkeypatch.setattr(PATH_ADV, lambda *_a, **_k: (5, 5, False, 1, 1), raising=True)

    # Use real jobs footer but capture its output
    marks: list[str] = []
    monkeypatch.setattr(st, "markdown", lambda msg: marks.append(msg), raising=True)
    monkeypatch.setattr(st, "caption", _no_ui, raising=True)

    # Widgets needed by public flow
    monkeypatch.setattr(st, "divider", _no_ui, raising=True)
    monkeypatch.setattr(st, "subheader", _no_ui, raising=True)
    monkeypatch.setattr(st, "selectbox", lambda *_a, **_k: AgentMode.RULE_BASED.value, raising=True)
    monkeypatch.setattr(st, "checkbox", lambda *_a, **_k: False, raising=True)

    _ = uis.render_sidebar_controls(settings)
    assert any("job-123" in m for m in marks)
