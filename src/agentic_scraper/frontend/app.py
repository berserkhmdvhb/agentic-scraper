from __future__ import annotations

import asyncio
import sys

import streamlit as st

from agentic_scraper.backend.config.messages import MSG_UI_RESET_COMPLETE
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.frontend.app_helpers import (
    configure_app_page,
    make_render_jobs,
    make_render_run,
    render_main_tabs,
    reset_app_state,
    setup_logging_and_logger,
)
from agentic_scraper.frontend.ui_auth import authenticate_user

# --- WINDOWS ASYNCIO FIX ---
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def main() -> None:
    """Main entry point for the Streamlit frontend application."""
    # --- LOGGING SETUP ---
    logger = setup_logging_and_logger()

    # --- SETTINGS LOAD ---
    settings = get_settings()

    # --- AUTH FIRST (so sidebar can reflect pending state) ---
    authenticate_user()

    # --- Flash messages (post-reset confirmation) ---
    if st.session_state.pop("flash_reset_success", False):
        st.toast(MSG_UI_RESET_COMPLETE)

    # --- Init overlay state early ---
    if "show_auth_overlay" not in st.session_state:
        st.session_state["show_auth_overlay"] = True

    # --- PAGE CONFIG AND SIDEBAR ---
    controls, raw_input = configure_app_page(settings)
    agent_mode = controls.agent_mode
    is_llm_mode = agent_mode != AgentMode.RULE_BASED

    # --- AUTH-GATED UX ---
    can_run = True
    if is_llm_mode:
        pending = st.session_state.get("auth_pending", False)
        not_logged_in = "jwt_token" not in st.session_state

        if pending:
            st.sidebar.info("Logging you in…")
            can_run = False  # prevent starting runs mid-login

        if not_logged_in and not pending and st.session_state.get("show_auth_overlay", True):
            st.info("🔐 Please log in to run LLM-based extraction.")

        can_run = can_run and (not not_logged_in)

    # --- OPTIONAL REMINDER ---
    if agent_mode.value.startswith("llm_") and "openai_credentials" not in st.session_state:
        st.info("👉 Submit your OpenAI API credentials in the sidebar before running extraction.")

    # --- SESSION STATE INIT ---
    if "is_running" not in st.session_state:
        st.session_state["is_running"] = False
    input_ready = (raw_input or "").strip()

    # === Controlled navigation ===
    run_renderer = make_render_run(
        input_ready=input_ready,
        can_run=can_run,
        raw_input=raw_input,
        controls=controls,
        logger=logger,
    )
    jobs_renderer = make_render_jobs()
    render_main_tabs(run_renderer, jobs_renderer)

    # --- RESET BUTTON ---
    reset_app_state(logger)


if __name__ == "__main__":
    main()
