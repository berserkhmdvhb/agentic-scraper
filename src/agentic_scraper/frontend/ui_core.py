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
from agentic_scraper.backend.core.settings import Settings, get_environment, get_log_dir

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
    # --- Agent Mode ---
    selected_agent_mode = st.sidebar.selectbox(
        "🧠 Agent Mode",
        options=sorted(VALID_AGENT_MODES),
        index=sorted(VALID_AGENT_MODES).index(DEFAULT_AGENT_MODE),
        key="agent_mode_select",
        help=(
            "Choose how the agent extracts structured data:\n\n"
            "- `llm-fixed`: Extracts a fixed set of fields (title, description,\n"
            "  price, etc.) using an LLM.\n"
            "- `llm-dynamic`: LLM analyzes the page and decides which fields are\n"
            "  relevant based on context.\n"
            "- `llm-dynamic-adaptive`: Builds on dynamic mode with smarter behavior:\n"
            "    ↳ Self-healing prompt loop if key fields are missing\n"
            "    ↳ Uses meta tags, URL paths, or breadcrumbs for better inference\n"
            "    ↳ Prioritizes important fields like title, price, and summary\n"
            "- `rule-based`: Uses lightweight regex and text heuristics (no LLM)."
        ),
    )

    # --- OpenAI Model ---
    if selected_agent_mode != "rule-based":
        selected_model = st.sidebar.selectbox(
            "🤖 OpenAI Model",
            options=list(VALID_MODEL_OPTIONS.keys()),
            index=list(VALID_MODEL_OPTIONS.keys()).index(DEFAULT_OPENAI_MODEL),
            format_func=lambda key: VALID_MODEL_OPTIONS[key],
            key="openai_model_select",
            help="Choose which OpenAI model to use for LLM-powered parsing.",
        )
    else:
        selected_model = None

    screenshot_enabled = st.sidebar.checkbox("📸 Enable Screenshot", value=False)

    with st.sidebar.expander("⚙️ Performance Settings", expanded=False):
        st.markdown("### 🔁 Concurrency")

        # Rule-based skips LLM concurrency split
        is_llm_agent = selected_agent_mode != "rule-based"

        if is_llm_agent:
            split = st.checkbox(
                "🔧 Separate fetch and LLM controls",
                help=(
                    "Enable this to control fetch and LLM concurrency separately.\n\n"
                    "Useful if:\n"
                    "• You want to fetch many pages but limit OpenAI load.\n"
                    "• You're tuning for different I/O vs compute bottlenecks."
                ),
            )
        else:
            split = False  # Disable for rule-based

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
            # Combined concurrency label + help depends on agent type
            concurrency_label = (
                "🔁 Max concurrency (fetch + LLM)" if is_llm_agent else "🔁 Fetch Concurrency"
            )
            concurrency_help = (
                (
                    "Controls how many tasks run in parallel.\n\n"
                    "1. 🌐 Fetching: Limits how many web pages are fetched at the same time.\n"
                    "2. 🤖 LLM: Limits how many pages are processed by the AI model at once.\n\n"
                    "⚠️ High values may improve speed,\n"
                    "   but could hit rate limits or cause instability."
                )
                if is_llm_agent
                else (
                    "Controls how many web pages are fetched in parallel.\n\n"
                    "This mode does not use LLMs, so concurrency applies only to fetching."
                )
            )

            concurrency = st.slider(
                concurrency_label,
                min_value=1,
                max_value=20,
                value=10,
                help=concurrency_help,
            )
            fetch_concurrency = concurrency
            llm_concurrency = concurrency if is_llm_agent else 0

        # --- Verbosity ---
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

        retry_attempts = st.slider(
            "♻️ Retry Attempts",
            min_value=0,
            max_value=5,
            value=1,
            help="How many times to retry failed fetches or LLM calls. "
            "Useful for unstable connections or rate-limited sites.",
        )

        llm_schema_placeholder = st.empty()

        if selected_agent_mode == "llm-dynamic-adaptive":
            with llm_schema_placeholder:
                llm_schema_retries = st.slider(
                    "🧠 LLM Schema Retries",
                    min_value=0,
                    max_value=5,
                    value=2,
                    key="llm_schema_retries",  # ensure widget state is preserved
                    help=(
                        "How many times to retry LLM extraction if required fields are missing.\n\n"
                        "🔁 Useful when the AI omits key data (e.g. price, title).\n"
                        "⚠️ Higher values increase latency and token cost."
                    ),
                )
        else:
            llm_schema_placeholder.empty()
            llm_schema_retries = Settings().llm_schema_retries

    # --- Store in session state ---
    st.session_state["screenshot_enabled"] = screenshot_enabled
    st.session_state["fetch_concurrency"] = fetch_concurrency
    st.session_state["llm_concurrency"] = llm_concurrency
    st.session_state["verbose"] = verbose
    st.session_state["openai_model"] = selected_model
    st.session_state["agent_mode"] = selected_agent_mode
    st.session_state["retry_attempts"] = retry_attempts
    st.session_state["llm_schema_retries"] = llm_schema_retries

    return {
        "screenshot_enabled": screenshot_enabled,
        "fetch_concurrency": fetch_concurrency,
        "llm_concurrency": llm_concurrency,
        "verbose": verbose,
        "openai_model": selected_model,
        "agent_mode": selected_agent_mode,
        "retry_attempts": retry_attempts,
        "llm_schema_retries": llm_schema_retries,
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
