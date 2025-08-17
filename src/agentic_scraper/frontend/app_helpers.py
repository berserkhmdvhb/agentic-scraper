from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import streamlit as st

from agentic_scraper.backend.config.messages import (
    MSG_EXCEPTION_UNEXPECTED_PIPELINE_ERROR,
    MSG_INFO_APP_RESET_TRIGGERED,
)
from agentic_scraper.backend.config.types import AllowedTab
from agentic_scraper.backend.core.logger_setup import get_logger, setup_logging
from agentic_scraper.frontend.models import PipelineConfig, SidebarConfig
from agentic_scraper.frontend.ui_jobs import render_jobs_tab
from agentic_scraper.frontend.ui_page_config import configure_page, render_input_section
from agentic_scraper.frontend.ui_runner import submit_scrape_job
from agentic_scraper.frontend.ui_sidebar import render_sidebar_controls

if TYPE_CHECKING:
    from agentic_scraper.backend.core.settings import Settings


# --------------------------------------------------------------------
# Navigation constants and helpers
# --------------------------------------------------------------------


def coerce_tab_value(value: object, *, default: AllowedTab = AllowedTab.RUN) -> AllowedTab:
    """
    Map legacy/invalid values to a valid AllowedTab.
    Accepts: exact Enum values, case-insensitive strings ("run", "jobs"),
    single letters ("R", "J"), ints (0,1), and numeric strings ("0","1").
    """
    result: AllowedTab = default

    if isinstance(value, AllowedTab):
        result = value
    elif isinstance(value, str):
        v = value.strip()
        try:
            result = AllowedTab(v)
        except ValueError:
            low = v.lower()
            if low.startswith("run") or low == "r":
                result = AllowedTab.RUN
            elif low.startswith("job") or low == "j":
                result = AllowedTab.JOBS
            elif low == "0":
                result = AllowedTab.RUN
            elif low == "1":
                result = AllowedTab.JOBS
    elif isinstance(value, int):
        result = AllowedTab.RUN if value == 0 else AllowedTab.JOBS

    return result


def render_main_tabs(
    render_run: Callable[[], None],
    render_jobs: Callable[[str | None], None],
) -> None:
    """
    Controlled navigation with AllowedTab Enum.
    Normalizes legacy values and query params before widget creation.
    """
    # 1) Normalize from query param
    qp = st.query_params.get("tab", [AllowedTab.RUN.value])
    qp_val = qp[0] if isinstance(qp, list) and qp else AllowedTab.RUN.value
    tab_from_query = coerce_tab_value(qp_val)

    # 2) Migrate/normalize legacy session values BEFORE widget creation
    legacy = st.session_state.get("main_tab", None)
    if legacy is None:
        # migrate from old 'active_tab' if present
        legacy = st.session_state.pop("active_tab", None)

    # 2.5) Apply any pending navigation intent BEFORE creating the widget
    pending = st.session_state.pop("pending_main_tab", None)
    if pending is not None:
        st.session_state["main_tab"] = coerce_tab_value(pending, default=tab_from_query)
    else:
        st.session_state["main_tab"] = coerce_tab_value(legacy, default=tab_from_query)

    # 3) Create the control with safe defaults and coerce the return to AllowedTab
    main_tab: AllowedTab = coerce_tab_value(
        st.segmented_control(
            " ",
            options=[AllowedTab.RUN, AllowedTab.JOBS],
            format_func=lambda x: x.value,  # display "Run"/"Jobs"
            key="main_tab",
        )
    )

    # 4) Keep URL in sync (pretty)
    st.query_params["tab"] = main_tab.value

    # 5) Render selected view
    if main_tab is AllowedTab.RUN:
        render_run()
    else:
        # Prefer one-shot preselect set by switch_to_jobs(), fallback to last_job_id
        pre_id = st.session_state.pop("preselect_job_id", None)
        if pre_id is None:
            pre_id = st.session_state.get("last_job_id")
        render_jobs(pre_id)


def switch_to_jobs(preselect_job_id: str | None = None) -> None:
    """Switch to Jobs and optionally remember a job to preselect."""
    if preselect_job_id:
        st.session_state["preselect_job_id"] = preselect_job_id
        st.session_state["last_job_id"] = preselect_job_id
    st.session_state["pending_main_tab"] = AllowedTab.JOBS
    st.rerun()


# --------------------------------------------------------------------
# Run log (persist messages across reruns)
# --------------------------------------------------------------------
def runlog_add(kind: str, text: str) -> None:
    """Append a message to the Run log (persists across reruns)."""
    st.session_state.setdefault("run_log", []).append((kind, text))


def runlog_clear() -> None:
    """Clear the Run log."""
    st.session_state["run_log"] = []


def runlog_render() -> None:
    """Render all messages in the Run log."""
    for kind, text in st.session_state.get("run_log", []):
        getattr(st, kind)(text)


# --------------------------------------------------------------------
# Existing helpers
# --------------------------------------------------------------------
def setup_logging_and_logger() -> logging.Logger:
    """Initialize logging system and return logger."""
    setup_logging(reset=True)
    return get_logger()


def configure_app_page(settings: Settings) -> tuple[SidebarConfig, str]:
    """Render the app layout, sidebar controls, and input method section."""
    configure_page()
    return render_sidebar_controls(settings), render_input_section()


def submit_run(raw_input: str, controls: SidebarConfig) -> None:
    """
    Submit a scrape job and switch to Jobs tab on success.
    """
    config = PipelineConfig(**controls.model_dump())
    job_id = submit_scrape_job(raw_input, config)
    if job_id:
        switch_to_jobs(preselect_job_id=job_id)


def handle_run_button(input_ready: str, *, can_run: bool) -> None:
    """Render the Run button and handle submit intent."""
    if "run_submitting" not in st.session_state:
        st.session_state["run_submitting"] = False

    disabled = (not can_run) or st.session_state["run_submitting"]
    clicked = st.button("🚀 Run Extraction", type="primary", disabled=disabled)
    if clicked:
        if not input_ready.strip():
            st.warning("⚠️ Please provide at least one URL or upload a .txt file.")
            return
        st.session_state["run_submitting"] = True
        st.rerun()


def process_pipeline(raw_input: str, controls: SidebarConfig, logger: logging.Logger) -> None:
    """
    Kick off the job creation and navigate to Jobs tab on success.
    Uses the run log so messages persist across reruns.
    """
    try:
        runlog_clear()
        runlog_add("info", "Starting job…")
        submit_run(raw_input, controls)  # Will switch & rerun on success
        runlog_add("warning", "⚠️ Job could not be created.")
    except Exception:
        logger.exception(MSG_EXCEPTION_UNEXPECTED_PIPELINE_ERROR)
        runlog_add("error", "❌ An unexpected error occurred while starting the job.")
    finally:
        st.session_state["run_submitting"] = False


def reset_app_state(logger: logging.Logger) -> None:
    """
    Render a reset button that clears most session state,
    but preserves login and OpenAI credentials.
    """
    if st.sidebar.button("🔄 Reset"):
        logger.info(MSG_INFO_APP_RESET_TRIGGERED)
        preserved_keys = {
            "jwt_token",
            "user_info",
            "openai_credentials",
            "openai_credentials_preview",
        }
        keys_to_clear = [k for k in st.session_state if k not in preserved_keys]
        for key in keys_to_clear:
            del st.session_state[key]
        st.session_state["flash_reset_success"] = True
        st.rerun()


# --------------------------------------------------------------------
# Render factories (so app.py stays tiny and typed)
# --------------------------------------------------------------------
def make_render_run(
    *,
    input_ready: str,
    can_run: bool,
    raw_input: str,
    controls: SidebarConfig,
    logger: logging.Logger,
) -> Callable[[], None]:
    """
    Build a zero-arg renderer for the Run tab.
    Imported in app.py and passed to render_main_tabs().
    """

    def _render_run() -> None:
        runlog_render()
        handle_run_button(input_ready, can_run=can_run)
        if st.session_state.get("run_submitting", False):
            process_pipeline(raw_input, controls, logger)

    return _render_run


def make_render_jobs() -> Callable[[str | None], None]:
    """
    Build a renderer for the Jobs tab that accepts an optional preselect_job_id.
    Imported in app.py and passed to render_main_tabs().
    """

    def _render_jobs(preselect_job_id: str | None = None) -> None:
        render_jobs_tab(preselect_job_id=preselect_job_id)

    return _render_jobs
