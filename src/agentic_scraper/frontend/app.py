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
import sys

import streamlit as st

from agentic_scraper.backend.config.messages import MSG_UI_RESET_COMPLETE
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.frontend.app_helpers import (
    configure_app_page,
    handle_run_button,
    process_pipeline,
    reset_app_state,
    setup_logging_and_logger,
)
from agentic_scraper.frontend.ui_auth import authenticate_user
from agentic_scraper.frontend.ui_jobs import render_jobs_tab

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
    # Default True so first-time users see the login CTA if needed.
    if "show_auth_overlay" not in st.session_state:
        st.session_state["show_auth_overlay"] = True

    # --- Track which tab should be active: 0 = Run, 1 = Jobs ---
    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = 0

    # --- PAGE CONFIG AND SIDEBAR ---
    controls, raw_input = configure_app_page(settings)
    agent_mode = controls.agent_mode
    is_llm_mode = agent_mode != AgentMode.RULE_BASED

    # --- AUTH-GATED UX ---
    can_run = True
    if is_llm_mode:
        pending = st.session_state.get("auth_pending", False)
        not_logged_in = "jwt_token" not in st.session_state

        # If pending, show a lightweight reminder in sidebar (login_ui hides the button)
        if pending:
            st.sidebar.info("Logging you in…")
            can_run = False  # prevent starting runs mid-login

        # Top-of-page nudge (optional) when not logged in and not pending
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
