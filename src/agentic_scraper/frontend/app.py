import asyncio
import sys

import streamlit as st

from agentic_scraper.backend.config.messages import MSG_EXCEPTION_UNEXPECTED_PIPELINE_ERROR
from agentic_scraper.backend.core.logger_setup import get_logger, setup_logging
from agentic_scraper.backend.core.settings import get_settings, log_settings
from agentic_scraper.frontend.ui_core import (
    configure_page,
    render_input_section,
    render_sidebar_controls,
)
from agentic_scraper.frontend.ui_display import display_results
from agentic_scraper.frontend.ui_runner import maybe_run_pipeline

# --- WINDOWS ASYNCIO FIX ---
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def main() -> None:
    # --- LOGGING SETUP ---
    setup_logging(reset=True)
    logger = get_logger()

    # --- PAGE CONFIGURATION ---
    configure_page()

    # --- RENDER SIDEBAR AND INPUTS ---
    controls = render_sidebar_controls()
    raw_input = render_input_section()

    # --- SESSION STATE INIT ---
    if "is_running" not in st.session_state:
        st.session_state["is_running"] = False

    # --- RUN EXTRACTION BUTTON ---
    if not st.session_state["is_running"]:
        run_button = st.button("🚀 Run Extraction", type="primary")
        if run_button:
            if not raw_input.strip():
                st.warning("⚠️ Please provide at least one URL or upload a .txt file.")
            else:
                st.session_state["is_running"] = True
                st.rerun()
    else:
        st.button("🚀 Run Extraction", disabled=True)

    # --- PROCESSING PIPELINE ---
    if st.session_state["is_running"]:
        try:
            # Log effective settings based on user overrides
            effective_settings = get_settings().model_copy(
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
                raw_input=raw_input,
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

    # --- RESET BUTTON ---
    if st.sidebar.button("🔄 Reset"):
        st.session_state.clear()
        st.rerun()


if __name__ == "__main__":
    main()
