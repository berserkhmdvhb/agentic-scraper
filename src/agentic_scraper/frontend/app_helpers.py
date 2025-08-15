from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import streamlit as st

from agentic_scraper.backend.config.messages import (
    MSG_EXCEPTION_UNEXPECTED_PIPELINE_ERROR,
    MSG_INFO_APP_RESET_TRIGGERED,
)
from agentic_scraper.backend.core.logger_setup import get_logger, setup_logging
from agentic_scraper.frontend.models import PipelineConfig, SidebarConfig
from agentic_scraper.frontend.ui_page_config import configure_page, render_input_section
from agentic_scraper.frontend.ui_runner import submit_scrape_job
from agentic_scraper.frontend.ui_sidebar import render_sidebar_controls

if TYPE_CHECKING:
    from agentic_scraper.backend.core.settings import Settings


# --------------------------------------------------------------------
# Navigation constants and helpers
# --------------------------------------------------------------------
DEFAULT_TAB = "Run"
TAB_RUN = "Run"
TAB_JOBS = "Jobs"


def render_main_tabs(
    render_run: Callable[[], None], render_jobs: Callable[[str | None], None]
) -> None:
    """
    Controlled navigation: render a segmented control and call the appropriate tab renderer.
    Keeps URL ?tab=... in sync for deep-linking.

    Args:
        render_run: Callable that renders the Run tab content.
        render_jobs:
            Callable that renders the Jobs tab content.
            Accepts an optional preselect_job_id.
    """
    if "main_tab" not in st.session_state:
        st.session_state["main_tab"] = st.query_params.get("tab", [DEFAULT_TAB])[0]

    main_tab = st.segmented_control(" ", options=[TAB_RUN, TAB_JOBS], key="main_tab")
    st.query_params["tab"] = main_tab

    if main_tab == TAB_RUN:
        render_run()
    else:
        pre_id = st.session_state.get("last_job_id")
        render_jobs(pre_id)


def switch_to_jobs(preselect_job_id: str | None = None) -> None:
    """
    Switch the UI to the Jobs tab and optionally remember a job to preselect.

    Args:
        preselect_job_id: ID of the job to preselect in the Jobs tab.
    """
    if preselect_job_id:
        st.session_state["last_job_id"] = preselect_job_id
    st.session_state["main_tab"] = TAB_JOBS
    st.rerun()


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
    """
    try:
        st.info("Starting job…")
        submit_run(raw_input, controls)  # Will switch & rerun on success
        st.warning("⚠️ Job could not be created.")  # Only shown if no job_id
    except Exception:
        logger.exception(MSG_EXCEPTION_UNEXPECTED_PIPELINE_ERROR)
        st.error("❌ An unexpected error occurred while starting the job.")
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
