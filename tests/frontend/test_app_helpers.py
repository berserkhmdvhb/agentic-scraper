from __future__ import annotations

import logging
from collections.abc import Mapping
from types import TracebackType
from typing import TYPE_CHECKING

import pytest
import streamlit as st

from agentic_scraper.backend.config.types import AgentMode, AllowedTab
from agentic_scraper.frontend import app_helpers as ah
from agentic_scraper.frontend.models import SidebarConfig

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

    from agentic_scraper.backend.core.settings import Settings
    from agentic_scraper.frontend.models import PipelineConfig


# ----------------------------- coerce_tab_value -----------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (AllowedTab.RUN, AllowedTab.RUN),
        ("Run", AllowedTab.RUN),
        ("run", AllowedTab.RUN),
        ("r", AllowedTab.RUN),
        ("0", AllowedTab.RUN),
        (0, AllowedTab.RUN),
        (AllowedTab.JOBS, AllowedTab.JOBS),
        ("Jobs", AllowedTab.JOBS),
        ("jobs", AllowedTab.JOBS),
        ("j", AllowedTab.JOBS),
        ("1", AllowedTab.JOBS),
        (1, AllowedTab.JOBS),
        ("weird", AllowedTab.RUN),
        (object(), AllowedTab.RUN),
    ],
)
def test_coerce_tab_value(value: object, expected: AllowedTab) -> None:
    assert ah.coerce_tab_value(value) is expected


# ----------------------------- render_main_tabs -----------------------------


class _QP:
    """Minimal query_params shim: supports get(key, default) and item assignment."""

    def __init__(self, initial: dict[str, list[str]] | None = None) -> None:
        self._d: dict[str, list[str]] = dict(initial or {})

    def get(self, key: str, default: list[str] | None = None) -> list[str] | None:
        return self._d.get(key, default)

    def __setitem__(self, key: str, value: list[str] | str) -> None:
        # The production code assigns a string; normalize to list[str]
        self._d[key] = [value] if isinstance(value, str) else value


def test_render_main_tabs_renders_run_and_jobs(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    monkeypatch.setattr(st, "query_params", _QP({"tab": ["Run"]}), raising=True)

    rendered = {"run": 0, "jobs": 0}

    def _render_run() -> None:
        rendered["run"] += 1

    def _render_jobs(_pre: str | None) -> None:
        rendered["jobs"] += 1

    # First: RUN path
    monkeypatch.setattr(st, "segmented_control", lambda *_a, **_k: AllowedTab.RUN, raising=True)
    ah.render_main_tabs(_render_run, _render_jobs)
    assert rendered == {"run": 1, "jobs": 0}
    assert st.query_params.get("tab", [""])[0] == AllowedTab.RUN.value

    # Simulate a pending switch to JOBS with preselect id.
    st.session_state["preselect_job_id"] = "jid-1"
    st.session_state["pending_main_tab"] = AllowedTab.JOBS
    # (we'll patch to return JOBS)
    monkeypatch.setattr(st, "segmented_control", lambda *_a, **_k: AllowedTab.JOBS, raising=True)
    ah.render_main_tabs(_render_run, _render_jobs)

    assert rendered == {"run": 1, "jobs": 1}
    assert st.query_params.get("tab", [""])[0] == AllowedTab.JOBS.value
    # preselect should be consumed
    assert "preselect_job_id" not in st.session_state


# ----------------------------- switch_to_jobs -----------------------------


def test_switch_to_jobs_sets_flags_and_reruns(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    calls = {"rerun": 0}

    def _rr() -> None:
        calls["rerun"] += 1

    monkeypatch.setattr(st, "rerun", _rr, raising=True)

    ah.switch_to_jobs(preselect_job_id="abc-123")
    assert st.session_state["preselect_job_id"] == "abc-123"
    assert st.session_state["last_job_id"] == "abc-123"
    assert st.session_state["pending_main_tab"] is AllowedTab.JOBS
    assert calls["rerun"] == 1


# ----------------------------- run log -----------------------------


def test_runlog_add_clear_render(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    out: list[str] = []

    monkeypatch.setattr(st, "info", lambda m: out.append(f"I:{m}"), raising=True)
    monkeypatch.setattr(st, "warning", lambda m: out.append(f"W:{m}"), raising=True)
    monkeypatch.setattr(st, "error", lambda m: out.append(f"E:{m}"), raising=True)

    ah.runlog_add("info", "hello")
    ah.runlog_add("warning", "careful")
    ah.runlog_add("error", "oops")

    ah.runlog_render()
    assert out == ["I:hello", "W:careful", "E:oops"]

    ah.runlog_clear()
    out.clear()
    ah.runlog_render()
    assert out == []


# ----------------------------- setup_logging_and_logger -----------------------------


def test_setup_logging_and_logger(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    calls = {"setup": 0, "get": 0}

    def _setup_logging(*, reset: bool) -> None:
        assert reset is True
        calls["setup"] += 1

    class _Logger(logging.Logger):
        pass

    def _get_logger() -> logging.Logger:
        calls["get"] += 1
        return _Logger("x")

    monkeypatch.setattr(ah, "setup_logging", _setup_logging, raising=True)
    monkeypatch.setattr(ah, "get_logger", _get_logger, raising=True)

    logger = ah.setup_logging_and_logger()
    assert isinstance(logger, logging.Logger)
    assert calls == {"setup": 1, "get": 1}


# ----------------------------- configure_app_page -----------------------------


def _make_sidebar_config() -> SidebarConfig:
    return SidebarConfig(
        screenshot_enabled=False,
        fetch_concurrency=5,
        llm_concurrency=3,
        verbose=True,
        openai_model=None,
        agent_mode=AgentMode.RULE_BASED,
        retry_attempts=1,
        llm_schema_retries=0,
    )


def test_configure_app_page_calls(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    calls = {"page": 0, "sidebar": 0, "input": 0}

    cfg = _make_sidebar_config()

    def _configure_page() -> None:
        calls["page"] += 1

    def _render_sidebar_controls(_settings: Settings) -> SidebarConfig:
        calls["sidebar"] += 1
        return cfg

    def _render_input_section() -> str:
        calls["input"] += 1
        return "urls"

    monkeypatch.setattr(ah, "configure_page", _configure_page, raising=True)
    monkeypatch.setattr(ah, "render_sidebar_controls", _render_sidebar_controls, raising=True)
    monkeypatch.setattr(ah, "render_input_section", _render_input_section, raising=True)

    out_cfg, mode = ah.configure_app_page(ah.load_settings())
    assert out_cfg == cfg
    assert mode == "urls"
    assert calls == {"page": 1, "sidebar": 1, "input": 1}


# ----------------------------- submit_run -----------------------------


def test_submit_run_switches_to_jobs(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    cfg = _make_sidebar_config()
    seen: list[str | None] = []

    def _submit_scrape_job(_raw: str, _cfg: PipelineConfig) -> str | None:
        return "job-1"

    def _switch_to_jobs(preselect_job_id: str | None) -> None:
        seen.append(preselect_job_id)

    monkeypatch.setattr(ah, "submit_scrape_job", _submit_scrape_job, raising=True)
    monkeypatch.setattr(ah, "switch_to_jobs", _switch_to_jobs, raising=True)

    ah.submit_run("http://x", cfg)
    assert seen == ["job-1"]


def test_submit_run_no_job_id_no_switch(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    cfg = _make_sidebar_config()
    seen: list[str | None] = []

    def _submit_scrape_job(_raw: str, _cfg: PipelineConfig) -> str | None:
        return None

    def _switch_to_jobs(preselect_job_id: str | None) -> None:
        seen.append(preselect_job_id)

    monkeypatch.setattr(ah, "submit_scrape_job", _submit_scrape_job, raising=True)
    monkeypatch.setattr(ah, "switch_to_jobs", _switch_to_jobs, raising=True)

    ah.submit_run("http://x", cfg)
    assert seen == []


# ----------------------------- handle_run_button -----------------------------


def test_handle_run_button_basic_flow(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    # First call: button returns False -> nothing happens
    monkeypatch.setattr(st, "button", lambda *_a, **_k: False, raising=True)
    ah.handle_run_button("http://x", can_run=True)
    assert st.session_state.get("run_submitting") is False

    # Second: clicking with empty input -> warning
    marks: list[str] = []
    monkeypatch.setattr(st, "button", lambda *_a, **_k: True, raising=True)
    monkeypatch.setattr(st, "warning", lambda m: marks.append(str(m)), raising=True)
    ah.handle_run_button("", can_run=True)
    assert any("Please provide at least one URL" in m for m in marks)

    # Third: clicking with proper input -> flag set True
    ah.handle_run_button("http://x", can_run=True)
    assert st.session_state.get("run_submitting") is True


# ----------------------------- process_pipeline -----------------------------


def test_process_pipeline_success_path(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()

    def _submit_run(_raw: str, _cfg: SidebarConfig) -> None:
        return None

    monkeypatch.setattr(ah, "submit_run", _submit_run, raising=True)

    cfg = _make_sidebar_config()
    ah.process_pipeline("http://x", cfg, logging.getLogger("x"))

    # ensure flag reset
    assert st.session_state.get("run_submitting") is False


def test_process_pipeline_error_path(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    cfg = _make_sidebar_config()
    logged = {"exc": 0}

    class _Logger(logging.Logger):
        def exception(
            self,
            msg: object,
            *args: object,
            exc_info: bool
            | tuple[type[BaseException], BaseException, TracebackType | None]
            | tuple[None, None, None]
            | BaseException
            | None = False,
            stack_info: bool = False,
            stacklevel: int = 1,
            extra: Mapping[str, object] | None = None,
        ) -> None:
            _ = msg, args, exc_info, stack_info, stacklevel, extra  # mark used
            logged["exc"] += 1

    def _submit_run(_raw: str, _cfg: SidebarConfig) -> None:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(ah, "submit_run", _submit_run, raising=True)

    ah.process_pipeline("http://x", cfg, _Logger("x"))
    # flag reset and exception logged
    assert st.session_state.get("run_submitting") is False
    assert logged["exc"] == 1


# ----------------------------- reset_app_state -----------------------------


def test_reset_app_state_preserves_login_and_creds(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    st.session_state.update(
        {
            "jwt_token": "t",
            "user_info": {"u": 1},
            "openai_credentials": object(),
            "openai_credentials_preview": {"api_key": "sk-***"},
            "foo": 1,
            "bar": 2,
        }
    )

    calls = {"info": 0, "rerun": 0}

    class _Logger(logging.Logger):
        def info(
            self,
            msg: object,
            *args: object,
            exc_info: bool
            | tuple[type[BaseException], BaseException, TracebackType | None]
            | tuple[None, None, None]
            | BaseException
            | None = False,
            stack_info: bool = False,
            stacklevel: int = 1,
            extra: Mapping[str, object] | None = None,
        ) -> None:
            _ = msg, args, exc_info, stack_info, stacklevel, extra  # mark used
            calls["info"] += 1

    def _rr() -> None:
        calls["rerun"] += 1

    monkeypatch.setattr(st.sidebar, "button", lambda *_a, **_k: True, raising=True)
    monkeypatch.setattr(st, "rerun", _rr, raising=True)

    ah.reset_app_state(_Logger("x"))

    # Preserved
    assert "jwt_token" in st.session_state
    assert "openai_credentials" in st.session_state
    assert "openai_credentials_preview" in st.session_state
    # Cleared
    assert "foo" not in st.session_state
    assert "bar" not in st.session_state
    assert st.session_state.get("flash_reset_success") is True
    assert calls["info"] == 1
    assert calls["rerun"] == 1


# ----------------------------- render factories -----------------------------


def test_make_render_run_triggers_pipeline(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    cfg = _make_sidebar_config()
    calls = {"handle": 0, "pipeline": 0}

    def _handle(_input_ready: str, *, can_run: bool) -> None:
        _ = can_run
        calls["handle"] += 1
        # Simulate click already happened: set the flag to trigger pipeline.
        st.session_state["run_submitting"] = True

    def _pipeline(_raw: str, _controls: SidebarConfig, _logger: logging.Logger) -> None:
        calls["pipeline"] += 1

    monkeypatch.setattr(ah, "handle_run_button", _handle, raising=True)
    monkeypatch.setattr(ah, "process_pipeline", _pipeline, raising=True)

    renderer = ah.make_render_run(
        input_ready="http://x",
        can_run=True,
        raw_input="http://x",
        controls=cfg,
        logger=logging.getLogger("x"),
    )

    renderer()
    assert calls == {"handle": 1, "pipeline": 1}


def test_make_render_jobs_delegates(monkeypatch: MonkeyPatch) -> None:
    st.session_state.clear()
    seen: list[str | None] = []

    def _render(preselect_job_id: str | None = None) -> None:
        seen.append(preselect_job_id)

    monkeypatch.setattr(ah, "render_jobs_tab", _render, raising=True)

    r = ah.make_render_jobs()
    r("abc")
    assert seen == ["abc"]
