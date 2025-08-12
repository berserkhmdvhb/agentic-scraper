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
from agentic_scraper.backend.core.logger_setup import get_logger, setup_logging
from agentic_scraper.backend.core.settings import Settings, get_settings, log_settings
from agentic_scraper.frontend.models import PipelineConfig, SidebarConfig
from agentic_scraper.frontend.ui_auth import authenticate_user
from agentic_scraper.frontend.ui_display import display_results
from agentic_scraper.frontend.ui_jobs import render_jobs_tab  # <-- NEW
from agentic_scraper.frontend.ui_page_config import configure_page, render_input_section
from agentic_scraper.frontend.ui_runner import run_scraper_pipeline
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


def handle_run_button(input_ready: str, *, can_run: bool) -> None:
    """
    Render and handle logic for the 'Run Extraction' button.

    Args:
        input_ready: User-provided input (non-empty if ready).
        can_run: Whether the prerequisites (e.g., JWT for LLM modes) are met.
    """
    disabled = not can_run
    label = "🚀 Run Extraction"

    if not st.session_state.get("is_running", False):
        run_button = st.button(label, type="primary", disabled=disabled)
        if run_button:
            if not input_ready:
                st.warning("⚠️ Please provide at least one URL or upload a .txt file.")
            else:
                st.session_state["is_running"] = True
                st.rerun()
    else:
        st.button(label, disabled=True)


def process_pipeline(
    raw_input: str, controls: SidebarConfig, settings: Settings, logger: logging.Logger
) -> None:
    """
    Run the scraper pipeline with the selected configuration and display results.
    """
    try:
        effective_settings = settings.model_copy(
            update={
                "openai_model": controls.openai_model,
                "agent_mode": controls.agent_mode,
                "retry_attempts": controls.retry_attempts,
                "verbose": controls.verbose,
                "screenshot_enabled": controls.screenshot_enabled,
            }
        )
        log_settings(effective_settings)
        config = PipelineConfig(**controls.model_dump())

        items, skipped = run_scraper_pipeline(raw_input, config)

        if items:
            display_results(items, screenshot_enabled=config.screenshot_enabled)
        elif skipped == 0:
            st.error("No successful extractions.")
    except Exception:
        logger.exception(MSG_EXCEPTION_UNEXPECTED_PIPELINE_ERROR)
        st.error("❌ An unexpected error occurred while running the pipeline.")
    finally:
        st.session_state["is_running"] = False


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

    # --- PAGE CONFIG AND SIDEBAR ---
    controls, raw_input = configure_app_page(settings)
    agent_mode = controls.agent_mode
    is_llm_mode = agent_mode != "rule_based"

    # --- AUTH (LLM modes only) ---
    can_run = True
    if is_llm_mode:
        authenticate_user()
        not_logged_in = "jwt_token" not in st.session_state
        if not_logged_in and st.session_state.get("show_auth_overlay", True):
            st.info("🔐 Please log in to run LLM-based extraction.")
        can_run = not not_logged_in

    # --- OPTIONAL REMINDER ---
    if agent_mode.startswith("llm_") and "openai_credentials" not in st.session_state:
        st.info("👉 Submit your OpenAI API credentials in the sidebar before running extraction.")

    # --- SESSION STATE INIT ---
    if "is_running" not in st.session_state:
        st.session_state["is_running"] = False
    input_ready = (raw_input or "").strip()

    # === Tabs ===
    tabs = st.tabs(["🧪 Run", "🧭 Jobs"])
    with tabs[0]:
        # --- RUN EXTRACTION BUTTON ---
        handle_run_button(input_ready, can_run=can_run)

        # --- PROCESSING PIPELINE ---
        if st.session_state["is_running"]:
            process_pipeline(raw_input, controls, settings, logger)

    with tabs[1]:
        render_jobs_tab()

    # --- RESET BUTTON ---
    reset_app_state(logger)


if __name__ == "__main__":
    main()
