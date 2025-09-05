"""
Streamlit app scaffolding helpers (layout, navigation, and job submission glue).

Responsibilities:
- Initialize settings/logging and configure page scaffolding.
- Normalize navigation state (query params/session) and render main tabs.
- Bridge sidebar controls + input area to job submission and Jobs tab handoff.
- Maintain a lightweight "run log" that survives Streamlit reruns.
- Provide reset utilities that preserve auth & saved credentials.

Public API:
- `load_settings`: Cached loader for `Settings`.
- `render_main_tabs`: Navigation controller for Run/Jobs tabs.
- `switch_to_jobs`: Programmatic navigation to Jobs (with optional preselect).
- `runlog_add` / `runlog_clear` / `runlog_render`: Persisted run log helpers.
- `setup_logging_and_logger`: Initialize logging; return the app logger.
- `configure_app_page`: Render page + sidebar + input section; return sidebar cfg + raw input.
- `submit_run`: Create a scrape job and switch to Jobs on success.
- `handle_run_button`: Render the Run button and gate submission state.
- `process_pipeline`: Orchestrate job start + resilient run-log messaging.
- `reset_app_state`: Reset most UI/session state while preserving auth/creds.
- `make_render_run` / `make_render_jobs`: Tiny render factories for app.py.

Config:
- Reads runtime configuration via `get_settings()` (cached by `load_settings`).
- Messaging and enums come from `backend.config.*`.

Operational:
- Streamlit reruns: uses `st.session_state` for durable UI intent and run logs.
- Navigation: keeps `?tab=` query param in sync with the segmented control.
- Safety: preserves JWT and saved OpenAI creds when resetting state.

Usage:
    settings = load_settings()
    logger = setup_logging_and_logger()
    sidebar_cfg, raw_input = configure_app_page(settings)
    render = make_render_run(
        input_ready=raw_input, can_run=True, raw_input=raw_input,
        controls=sidebar_cfg, logger=logger
    )
    render_jobs = make_render_jobs()
    render_main_tabs(render, render_jobs)

Notes:
- All functions are UI-facing helpers; they intentionally avoid backend coupling
  beyond creating jobs via `submit_scrape_job` and rendering the Jobs tab.
"""

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
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.frontend.models import PipelineConfig, SidebarConfig
from agentic_scraper.frontend.ui_jobs import render_jobs_tab
from agentic_scraper.frontend.ui_page_config import configure_page, render_input_section
from agentic_scraper.frontend.ui_runner import submit_scrape_job
from agentic_scraper.frontend.ui_sidebar import render_sidebar_controls

if TYPE_CHECKING:
    from agentic_scraper.backend.core.settings import Settings

__all__ = [
    "coerce_tab_value",
    "configure_app_page",
    "handle_run_button",
    "load_settings",
    "make_render_jobs",
    "make_render_run",
    "process_pipeline",
    "render_main_tabs",
    "reset_app_state",
    "runlog_add",
    "runlog_clear",
    "runlog_render",
    "setup_logging_and_logger",
    "submit_run",
    "switch_to_jobs",
]


@st.cache_resource
def load_settings() -> Settings:
    """
    Load and cache global `Settings` (env + config parsing).

    Returns:
        Settings: The shared settings object (cached across reruns).

    Notes:
        - Marked as a Streamlit resource to avoid repeated parsing on each rerun.
    """
    return get_settings()


# --------------------------------------------------------------------
# Navigation constants and helpers
# --------------------------------------------------------------------


def coerce_tab_value(value: object, *, default: AllowedTab = AllowedTab.RUN) -> AllowedTab:
    """
    Normalize an arbitrary value to a valid `AllowedTab`.

    Accepts:
        - Exact Enum values (AllowedTab.RUN/JOBS)
        - Case-insensitive strings ("run", "jobs")
        - Abbreviations ("R", "J")
        - Ints (0 → RUN, 1 → JOBS)
        - Numeric strings ("0", "1")

    Args:
        value (object): Untrusted value from query params/session/legacy sources.
        default (AllowedTab): Fallback when `value` can't be coerced.

    Returns:
        AllowedTab: A valid tab enum.
    """
    result: AllowedTab = default

    if isinstance(value, AllowedTab):
        result = value
    elif isinstance(value, str):
        v = value.strip()
        try:
            # Try direct Enum construction first (e.g., "Run"/"Jobs")
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
    Render main Run/Jobs tabs with normalized navigation state.

    This keeps `?tab=` in sync, respects pending navigation intents, and
    gracefully migrates legacy session keys.

    Args:
        render_run (Callable[[], None]): Renderer for the Run tab.
        render_jobs (Callable[[str | None], None]): Renderer for Jobs tab (accepts preselect id).

    Returns:
        None
    """
    # 1) Normalize from query param. Supports both list and scalar forms from Streamlit.
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
    # Empty label (" ") keeps layout tidy while still rendering the segmented control.
    main_tab: AllowedTab = coerce_tab_value(
        st.segmented_control(
            " ",
            options=[AllowedTab.RUN, AllowedTab.JOBS],
            format_func=lambda x: x.value,  # display "Run"/"Jobs"
            key="main_tab",
        )
    )

    # 4) Keep URL in sync (pretty navigation & shareable links)
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
    """
    Programmatically switch to the Jobs tab and optionally preselect a job.

    Args:
        preselect_job_id (str | None): A job ID to highlight on arrival.

    Returns:
        None

    Notes:
        - Uses `pending_main_tab` to avoid fighting with current-frame UI state.
        - Triggers an immediate rerun to realize the navigation.
    """
    if preselect_job_id:
        st.session_state["preselect_job_id"] = preselect_job_id
        st.session_state["last_job_id"] = preselect_job_id
    st.session_state["pending_main_tab"] = AllowedTab.JOBS
    st.rerun()


# --------------------------------------------------------------------
# Run log (persist messages across reruns)
# --------------------------------------------------------------------
def runlog_add(kind: str, text: str) -> None:
    """
    Append a message to the run log.

    Args:
        kind (str): Streamlit method name (e.g., "info", "warning", "error").
        text (str): Human-readable message.

    Returns:
        None

    Notes:
        - The entire log is stored in `st.session_state["run_log"]`.
    """
    st.session_state.setdefault("run_log", []).append((kind, text))


def runlog_clear() -> None:
    """
    Clear the run log.

    Returns:
        None
    """
    st.session_state["run_log"] = []


def runlog_render() -> None:
    """
    Render all messages currently in the run log.

    Returns:
        None

    Notes:
        - Calls the corresponding Streamlit function by name (e.g., `st.info`).
    """
    for kind, text in st.session_state.get("run_log", []):
        getattr(st, kind)(text)


# --------------------------------------------------------------------
# Existing helpers
# --------------------------------------------------------------------
def setup_logging_and_logger() -> logging.Logger:
    """
    Initialize the logging system and return a configured logger.

    Returns:
        logging.Logger: The project logger (rooted via `get_logger()`).

    Notes:
        - Uses `reset=True` to ensure a clean handler configuration during app startup.
    """
    setup_logging(reset=True)
    return get_logger()


def configure_app_page(settings: Settings) -> tuple[SidebarConfig, str]:
    """
    Render the page header, sidebar controls, and input section.

    Args:
        settings (Settings): Global settings for seeding default control values.

    Returns:
        tuple[SidebarConfig, str]: (sidebar controls config, raw input string)
    """
    configure_page()
    return render_sidebar_controls(settings), render_input_section()


def submit_run(raw_input: str, controls: SidebarConfig) -> None:
    """
    Submit a scrape job and navigate to the Jobs tab on success.

    Args:
        raw_input (str): Newline-separated URLs from the UI.
        controls (SidebarConfig): Sidebar values to seed the pipeline config.

    Returns:
        None
    """
    # Convert sidebar selections to the pipeline-friendly model
    config = PipelineConfig(**controls.model_dump())

    # Create job; `submit_scrape_job` handles errors/toasts internally.
    job_id = submit_scrape_job(raw_input, config)
    if job_id:
        switch_to_jobs(preselect_job_id=job_id)


def handle_run_button(input_ready: str, *, can_run: bool) -> None:
    """
    Render the primary Run button and manage its submission lifecycle.

    Args:
        input_ready (str): Raw URL input; must be non-empty to proceed.
        can_run (bool): External gating flag (e.g., auth/validation).

    Returns:
        None

    Notes:
        - Uses `st.session_state["run_submitting"]` to prevent double-submits
          during reruns while a job is being created.
    """
    if "run_submitting" not in st.session_state:
        st.session_state["run_submitting"] = False

    disabled = (not can_run) or st.session_state["run_submitting"]
    clicked = st.button("🚀 Run Extraction", type="primary", disabled=disabled)

    if clicked:
        if not input_ready.strip():
            st.warning("⚠️ Please provide at least one URL or upload a .txt file.")
            return
        # Enter submitting state and rerun; process_pipeline() will handle the rest.
        st.session_state["run_submitting"] = True
        st.rerun()


def process_pipeline(raw_input: str, controls: SidebarConfig, logger: logging.Logger) -> None:
    """
    Kick off job creation and navigate to the Jobs tab on success.

    Uses the run log so messages persist across reruns.

    Args:
        raw_input (str): Raw multi-line URL input.
        controls (SidebarConfig): Sidebar selections.
        logger (logging.Logger): App logger for exception reporting.

    Returns:
        None
    """
    try:
        runlog_clear()
        runlog_add("info", "Starting job…")
        submit_run(raw_input, controls)  # Will switch & rerun on success
        # If we didn't rerun (no job id), surface a warning.
        runlog_add("warning", "⚠️ Job could not be created.")
    except Exception:
        # Keep UI resilient; details go to the logger.
        logger.exception(MSG_EXCEPTION_UNEXPECTED_PIPELINE_ERROR)
        runlog_add("error", "❌ An unexpected error occurred while starting the job.")
    finally:
        st.session_state["run_submitting"] = False


def reset_app_state(logger: logging.Logger) -> None:
    """
    Render a sidebar Reset button that clears session state except auth/creds.

    Preserves:
        - `jwt_token`
        - `user_info`
        - `openai_credentials`
        - `openai_credentials_preview`

    Args:
        logger (logging.Logger): App logger.

    Returns:
        None
    """
    if st.sidebar.button("🔄 Reset"):
        logger.info(MSG_INFO_APP_RESET_TRIGGERED)
        preserved_keys = {
            "jwt_token",
            "user_info",
            "openai_credentials",
            "openai_credentials_preview",
        }
        # Clear everything except preserved auth/creds keys.
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
    Build a zero-argument renderer for the Run tab.

    Intended to be created in `app.py` and passed into `render_main_tabs`.

    Args:
        input_ready (str): Current raw input buffer.
        can_run (bool): Whether the Run button should be enabled.
        raw_input (str): Raw input (used during submission).
        controls (SidebarConfig): Sidebar config to pass into the pipeline.
        logger (logging.Logger): Logger for error reporting.

    Returns:
        Callable[[], None]: A function that renders the Run tab.
    """

    def _render_run() -> None:
        # Show any prior messages from earlier frames/reruns.
        runlog_render()
        handle_run_button(input_ready, can_run=can_run)
        # If the user clicked Run in the previous frame, process the submission now.
        if st.session_state.get("run_submitting", False):
            process_pipeline(raw_input, controls, logger)

    return _render_run


def make_render_jobs() -> Callable[[str | None], None]:
    """
    Build a renderer for the Jobs tab that accepts an optional preselect_job_id.

    Intended to be created in `app.py` and passed into `render_main_tabs`.

    Returns:
        Callable[[str | None], None]: A function that renders the Jobs tab.
    """

    def _render_jobs(preselect_job_id: str | None = None) -> None:
        render_jobs_tab(preselect_job_id=preselect_job_id)

    return _render_jobs
