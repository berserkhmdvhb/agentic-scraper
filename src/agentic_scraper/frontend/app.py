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
from agentic_scraper.frontend.ui_auth import login_ui
from agentic_scraper.frontend.ui_display import display_results
from agentic_scraper.frontend.ui_page_config import configure_page
from agentic_scraper.frontend.ui_runner import maybe_run_pipeline
from agentic_scraper.frontend.ui_sidebar import render_input_section, render_sidebar_controls

# --- WINDOWS ASYNCIO FIX ---
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


# Setup logging and return logger instance
def setup_logging_and_logger() -> get_logger:
    setup_logging(reset=True)
    return get_logger()


# Configure page and render sidebar + input sections
def configure_app_page(settings: Settings) -> tuple:
    configure_page()
    return render_sidebar_controls(settings), render_input_section()


# Check user authentication and ensure jwt_token is present in session state
def check_authentication() -> bool:
    login_ui()
    if "jwt_token" not in st.session_state:
        st.warning("⚠️ Please log in to continue.", icon="⚠️")
        return False
    return True


# Handle run extraction button logic and state changes
def handle_run_button(input_ready: str) -> None:
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


# Process the extraction pipeline
def process_pipeline(
    raw_input: str, controls: dict, settings: Settings, logger: logging.Logger
) -> None:
    try:
        effective_settings = settings.model_copy(
            update={
                "openai_model": controls["openai_model"],
                "agent_mode": controls["agent_mode"],
                "retry_attempts": controls["retry_attempts"],
                "verbose": controls["verbose"],
                "screenshot_enabled": controls["screenshot_enabled"],
            }
        )
        log_settings(effective_settings)

        # Run the extraction pipeline
        items, skipped = maybe_run_pipeline(
            raw_input=raw_input or "",
            controls=controls,
        )

        if items:
            display_results(items, screenshot_enabled=controls["screenshot_enabled"])
        elif skipped == 0:
            st.error("No successful extractions.")
    except Exception as e:
        logger.exception(MSG_EXCEPTION_UNEXPECTED_PIPELINE_ERROR)
        st.error(f"❌ An unexpected error occurred: {e}")
    finally:
        st.session_state["is_running"] = False


# Reset application state when reset button is clicked
def reset_app_state(logger: logging.Logger) -> None:
    if st.sidebar.button("🔄 Reset"):
        logger.info(MSG_INFO_APP_RESET_TRIGGERED)
        st.session_state.clear()
        st.rerun()


# Main function to manage the app workflow
def main() -> None:
    # --- LOGGING SETUP ---
    logger = setup_logging_and_logger()

    # --- SETTINGS AND PAGE CONFIG ---
    settings = get_settings()
    controls, raw_input = configure_app_page(settings)

    # --- AUTHENTICATION ---
    if not check_authentication():
        return

    # --- SESSION STATE INIT ---
    if "is_running" not in st.session_state:
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
