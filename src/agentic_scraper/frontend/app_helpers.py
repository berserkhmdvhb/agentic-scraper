from __future__ import annotations

import logging
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


def setup_logging_and_logger() -> logging.Logger:
    """Initialize logging system and return logger."""
    setup_logging(reset=True)
    return get_logger()


def configure_app_page(settings: Settings) -> tuple[SidebarConfig, str]:
    """Render the app layout, sidebar controls, and input method section."""
    configure_page()
    return render_sidebar_controls(settings), render_input_section()


def submit_run(raw_input: str, controls: SidebarConfig) -> None:
    """Submit a scrape job and switch to Jobs tab."""
    config = PipelineConfig(**controls.model_dump())
    job_id = submit_scrape_job(raw_input, config)
    if job_id:
        st.session_state["last_job_id"] = job_id
        st.session_state["active_tab"] = 1


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
    """Kick off the job creation and guide user to the Jobs tab."""
    try:
        st.info("Starting job…")
        submit_run(raw_input, controls)
        st.info("📡 Job created. Please open the **Jobs** tab to monitor progress.")
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
