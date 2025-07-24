import asyncio
import sys
from typing import Any

import streamlit as st

from agentic_scraper.backend.config.constants import (
    DEFAULT_AGENT_MODE,
    DEFAULT_OPENAI_MODEL,
    VALID_AGENT_MODES,
    VALID_MODEL_OPTIONS,
)
from agentic_scraper.backend.core.logger_setup import setup_logging
from agentic_scraper.backend.core.settings import get_environment, get_log_dir

# Windows asyncio compatibility
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Setup logging once on app start
setup_logging(reset=True)


def configure_page() -> None:
    from agentic_scraper.backend.core.logger_setup import setup_logging  # noqa: PLC0415

    setup_logging(reset=True)
    st.set_page_config(page_title="Agentic Scraper", layout="wide")
    st.title("🕵️ Agentic Scraper")
    st.markdown("Extract structured data from any list of URLs using LLM-powered parsing.")
    st.sidebar.markdown(f"**Environment:** `{get_environment()}`")
    st.sidebar.markdown(f"**Log Path:** `{get_log_dir() / 'agentic_scraper.log'}`")


def render_sidebar_controls() -> dict[str, Any]:
    # --- OpenAI Model ---
    selected_model = st.sidebar.selectbox(
        "🤖 OpenAI Model",
        options=list(VALID_MODEL_OPTIONS.keys()),
        index=list(VALID_MODEL_OPTIONS.keys()).index(DEFAULT_OPENAI_MODEL),
        format_func=lambda key: VALID_MODEL_OPTIONS[key],
        key="openai_model_select",
        help="Choose which OpenAI model to use for LLM-powered parsing.",
    )

    # --- Agent Mode ---
    selected_agent_mode = st.sidebar.selectbox(
        "🧠 Agent Mode",
        options=sorted(VALID_AGENT_MODES),
        index=sorted(VALID_AGENT_MODES).index(DEFAULT_AGENT_MODE),
        key="agent_mode_select",
        help=(
            "Choose how the agent extracts structured data:\n\n"
            "- `fixed`: Extracts predefined fields (title, description, price, etc.)\n"
            "- `adaptive`: LLM dynamically decides which fields are relevant\n"
            "- `rule`: Heuristic rule-based parser (no LLM)"
        ),
    )

    screenshot_enabled = st.sidebar.checkbox("📸 Enable Screenshot", value=False)

    with st.sidebar.expander("⚙️ Performance Settings", expanded=False):
        st.markdown("### 🔁 Concurrency")

        split = st.checkbox(
            "🔧 Separate fetch and LLM controls",
            help=(
                "Enable this to control fetch and LLM concurrency separately.\n\n"
                "Useful if:\n"
                "• You want to fetch many pages but limit OpenAI load.\n"
                "• You're tuning for different I/O vs compute bottlenecks."
            ),
        )

        if split:
            fetch_concurrency = st.slider(
                "🌐 Fetch Concurrency",
                min_value=1,
                max_value=20,
                value=10,
                help="Max number of web pages fetched in parallel.",
            )
            llm_concurrency = st.slider(
                "🤖 LLM Concurrency",
                min_value=1,
                max_value=20,
                value=10,
                help="Max number of pages sent to the AI model concurrently.",
            )
        else:
            concurrency = st.slider(
                "🔁 Max concurrency (fetch + LLM)",
                min_value=1,
                max_value=20,
                value=10,
                help=(
                    "Controls how many tasks run in parallel.\n\n"
                    "1. 🌐 Fetching: Limits how many web pages are fetched at the same time.\n"
                    "2. 🤖 LLM: Limits how many pages are processed by the AI model at once.\n\n"
                    "⚠️ High values may improve speed, but could hit rate limits "
                    "or cause instability."
                ),
            )
            fetch_concurrency = llm_concurrency = concurrency

        st.markdown("### 📣 Verbosity")
        verbose_default = get_environment() == "DEV"
        verbose = st.checkbox(
            "🐞 Verbose error tracebacks",
            value=verbose_default,
            help=(
                "When enabled, logs the full Python traceback if a scraping task fails.\n\n"
                "✅ Use during development to debug issues.\n"
                "🚫 Disable in production for cleaner logs."
            ),
        )

    # Save values explicitly in session state for consistent access
    st.session_state["screenshot_enabled"] = screenshot_enabled
    st.session_state["fetch_concurrency"] = fetch_concurrency
    st.session_state["llm_concurrency"] = llm_concurrency
    st.session_state["verbose"] = verbose
    st.session_state["openai_model"] = selected_model
    st.session_state["agent_mode"] = selected_agent_mode

    return {
        "screenshot_enabled": screenshot_enabled,
        "fetch_concurrency": fetch_concurrency,
        "llm_concurrency": llm_concurrency,
        "verbose": verbose,
        "openai_model": selected_model,
        "agent_mode": selected_agent_mode,
    }


def render_input_section() -> str:
    input_method = st.radio("Input method:", ["Paste URLs", "Upload .txt file"], horizontal=True)

    if input_method == "Paste URLs":
        return st.text_area(
            "Enter one URL per line:",
            height=200,
            placeholder="https://example.com\nhttps://another.com",
        )
    if input_method == "Upload .txt file":
        uploaded_file = st.file_uploader("Upload a .txt file with URLs", type=["txt"])
        if uploaded_file:
            try:
                return uploaded_file.read().decode("utf-8")
            except UnicodeDecodeError:
                st.error("❌ Unable to decode file. Please upload a UTF-8 encoded .txt file.")
    return ""
