"""
Streamlit entry point for the AgenticScraper frontend.

This script:
- Initializes logging and settings
- Handles user authentication via Auth0
- Displays sidebar controls and input panel
- Allows users to submit URLs for LLM-based or rule-based extraction
- Runs the scraping pipeline and renders results with optional screenshots
"""

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
from agentic_scraper.frontend.ui_effects import render_login_highlight
from agentic_scraper.frontend.ui_page_config import configure_page, render_input_section
from agentic_scraper.frontend.ui_runner import run_scraper_pipeline
from agentic_scraper.frontend.ui_sidebar import render_sidebar_controls

# --- WINDOWS ASYNCIO FIX ---
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def setup_logging_and_logger() -> logging.Logger:
    """
    Initialize logging system and return logger.

    Returns:
        logging.Logger: Configured project logger.
    """
    setup_logging(reset=True)
    return get_logger()


def configure_app_page(settings: Settings) -> tuple[SidebarConfig, str]:
    """
    Render the app layout, sidebar controls, and input method section.

    Args:
        settings (Settings): Global settings for default values.

    Returns:
        tuple[SidebarConfig, str]: Sidebar config and user input string.
    """
    configure_page()
    return render_sidebar_controls(settings), render_input_section()


def handle_run_button(input_ready: str) -> None:
    """
    Render and handle logic for the 'Run Extraction' button.

    Args:
        input_ready (str): User-provided input (non-empty if ready).

    Returns:
        None
    """
    if not st.session_state["is_running"]:
        run_button = st.button("🚀 Run Extraction", type="primary")
        if run_button:
            if not input_ready:
                st.warning("⚠️ Please provide at least one URL or upload a .txt file.")
            else:
                st.session_state["is_running"] = True
                st.rerun()
    else:
        st.button("🚀 Run Extraction", disabled=True)


def process_pipeline(
    raw_input: str, controls: SidebarConfig, settings: Settings, logger: logging.Logger
) -> None:
    """
    Run the scraper pipeline with the selected configuration and display results.

    Args:
        raw_input (str): Raw URL input from the user.
        controls (SidebarConfig): Sidebar settings for the scrape.
        settings (Settings): Base application settings.
        logger (logging.Logger): Logger for error tracking.

    Returns:
        None
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
    except Exception as e:
        logger.exception(MSG_EXCEPTION_UNEXPECTED_PIPELINE_ERROR)
        st.error(f"❌ An unexpected error occurred: {e}")
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
    """
    Main entry point for the Streamlit frontend application.

    Returns:
        None
    """
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

    # --- CONDITIONAL AUTH ---
    is_llm_mode = agent_mode != "rule_based"
    if is_llm_mode:
        authenticate_user()
        is_logged_in = "jwt_token" in st.session_state  # ← Move here
        if not is_logged_in:
            render_login_highlight()

    # --- OPTIONAL REMINDER ---
    if agent_mode.startswith("llm_") and "openai_credentials" not in st.session_state:
        st.info("👉 Submit your OpenAI API credentials in the sidebar before running extraction.")

    # --- SESSION STATE INIT ---
    if not st.session_state.get("is_running", False):
        st.session_state["is_running"] = False
    input_ready = (raw_input or "").strip()

    # --- RUN EXTRACTION BUTTON ---
    handle_run_button(input_ready)

    # --- PROCESSING PIPELINE ---
    if st.session_state["is_running"]:
        process_pipeline(raw_input, controls, settings, logger)

    # --- RESET BUTTON ---
    reset_app_state(logger)


if __name__ == "__main__":
    main()
