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
from agentic_scraper.frontend.models import PipelineConfig
from agentic_scraper.frontend.ui_auth import authenticate_user, login_ui
from agentic_scraper.frontend.ui_auth_redirect import render_auth_redirect_handler
from agentic_scraper.frontend.ui_display import display_results
from agentic_scraper.frontend.ui_page_config import configure_page, render_input_section
from agentic_scraper.frontend.ui_runner import run_scraper_pipeline
from agentic_scraper.frontend.ui_runner_helpers import validate_and_deduplicate_urls
from agentic_scraper.frontend.ui_sidebar import render_sidebar_controls

# --- WINDOWS ASYNCIO FIX ---
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def setup_logging_and_logger() -> get_logger:
    setup_logging(reset=True)
    return get_logger()


def configure_app_page(settings: Settings) -> tuple:
    configure_page()
    return render_sidebar_controls(settings), render_input_section()


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

        valid_urls, _ = validate_and_deduplicate_urls(raw_input)
        config = PipelineConfig(**controls)
        items, skipped = asyncio.run(run_scraper_pipeline(valid_urls, config))

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
    if st.sidebar.button("🔄 Reset"):
        logger.info(MSG_INFO_APP_RESET_TRIGGERED)
        st.session_state.clear()
        st.rerun()


def main() -> None:
    # --- LOGGING SETUP ---
    logger = setup_logging_and_logger()

    # --- SETTINGS LOAD ---
    settings = get_settings()

    # --- AUTH TOKEN HANDLING ---
    authenticate_user()

    # --- PAGE CONFIG AND SIDEBAR ---
    controls, raw_input = configure_app_page(settings)
    agent_mode = controls.agent_mode

    # --- LOGIN UI ---
    login_ui(agent_mode)

    # --- OPTIONAL REMINDER ---
    if agent_mode.startswith("llm_") and "openai_credentials" not in st.session_state:
        st.info("👉 Submit your OpenAI API credentials in the sidebar before running extraction.")

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
