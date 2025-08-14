"""
Streamlit entry point for the AgenticScraper frontend.

This version aligns the UI with the RESTful job flow and adds a Jobs tab:
- Auth via Auth0 (JWT) when using LLM modes
- Submit URLs → create backend job → poll until completion
- Display results returned by the job's final payload
- Jobs tab: list, inspect, and cancel past jobs
"""

from __future__ import annotations

import asyncio
import logging
import sys

import streamlit as st

from agentic_scraper.backend.config.messages import (
    MSG_EXCEPTION_UNEXPECTED_PIPELINE_ERROR,
    MSG_INFO_APP_RESET_TRIGGERED,
)
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.core.logger_setup import get_logger, setup_logging
from agentic_scraper.backend.core.settings import Settings, get_settings
from agentic_scraper.frontend.models import PipelineConfig, SidebarConfig
from agentic_scraper.frontend.ui_auth import authenticate_user
from agentic_scraper.frontend.ui_jobs import render_jobs_tab
from agentic_scraper.frontend.ui_page_config import configure_page, render_input_section
from agentic_scraper.frontend.ui_runner import submit_scrape_job
from agentic_scraper.frontend.ui_sidebar import render_sidebar_controls

# --- WINDOWS ASYNCIO FIX ---
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def setup_logging_and_logger() -> logging.Logger:
    """Initialize logging system and return logger."""
    setup_logging(reset=True)
    return get_logger()


def configure_app_page(settings: Settings) -> tuple[SidebarConfig, str]:
    """Render the app layout, sidebar controls, and input method section."""
    configure_page()
    return render_sidebar_controls(settings), render_input_section()


# Add near other helpers
def submit_run(raw_input: str, controls: SidebarConfig) -> None:
    config = PipelineConfig(**controls.model_dump())
    job_id = submit_scrape_job(raw_input, config)
    if job_id:
        st.session_state["active_tab"] = 1


def handle_run_button(input_ready: str, *, can_run: bool) -> None:
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
    try:
        st.info("Starting job…")  # (moved here)
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
        preserved_keys = {"jwt_token", "user_info", "openai_credentials"}
        keys_to_clear = [k for k in st.session_state if k not in preserved_keys]
        for key in keys_to_clear:
            del st.session_state[key]
        st.rerun()


def main() -> None:
    """Main entry point for the Streamlit frontend application."""
    # --- LOGGING SETUP ---
    logger = setup_logging_and_logger()

    # --- SETTINGS LOAD ---
    settings = get_settings()

    # --- Init overlay state early ---
    if "show_auth_overlay" not in st.session_state:
        st.session_state["show_auth_overlay"] = False

    # --- Track which tab should be active: 0 = Run, 1 = Jobs ---
    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = 0

    # --- PAGE CONFIG AND SIDEBAR ---
    controls, raw_input = configure_app_page(settings)
    agent_mode = controls.agent_mode
    is_llm_mode = agent_mode != AgentMode.RULE_BASED

    # --- AUTH (LLM modes only) ---
    can_run = True
    if is_llm_mode:
        authenticate_user()
        not_logged_in = "jwt_token" not in st.session_state
        if not_logged_in and st.session_state.get("show_auth_overlay", True):
            st.info("🔐 Please log in to run LLM-based extraction.")
        can_run = not not_logged_in

    # --- OPTIONAL REMINDER ---
    if agent_mode.value.startswith("llm_") and "openai_credentials" not in st.session_state:
        st.info("👉 Submit your OpenAI API credentials in the sidebar before running extraction.")

    # --- SESSION STATE INIT ---
    if "is_running" not in st.session_state:
        st.session_state["is_running"] = False
    input_ready = (raw_input or "").strip()

    # === Tabs ===
    tabs = st.tabs(["🧪 Run", "🧭 Jobs"])
    run_tab, jobs_tab = tabs
    with run_tab:
        # --- RUN EXTRACTION BUTTON ---
        handle_run_button(input_ready, can_run=can_run)

        # If flagged as submitting, do the submit work now (non-blocking overall)
        if st.session_state.get("run_submitting", False):
            process_pipeline(raw_input, controls, logger)
            # Nudge + auto-switch
            st.info("📡 Job created. Opening **Jobs**…")
            st.session_state["active_tab"] = 1
            st.rerun()

    with jobs_tab:
        render_jobs_tab(preselect_job_id=st.session_state.get("last_job_id"))

    # --- RESET BUTTON ---
    reset_app_state(logger)


if __name__ == "__main__":
    main()
