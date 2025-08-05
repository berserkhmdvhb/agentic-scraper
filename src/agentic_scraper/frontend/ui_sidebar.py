"""
Sidebar controls for the Streamlit frontend of AgenticScraper.

This module renders the interactive sidebar UI for:
- Environment display and login/authentication
- OpenAI credentials input (conditional on login)
- Agent mode selection
- Model selection and screenshot toggle
- Advanced settings for concurrency, retries, and verbosity

Returns a `SidebarConfig` object with user-selected values to control scraping behavior.
"""

import streamlit as st

from agentic_scraper.backend.config.constants import SESSION_KEYS, VALID_MODEL_OPTIONS
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.core.settings import Settings, get_environment, get_log_dir
from agentic_scraper.frontend.models import SidebarConfig
from agentic_scraper.frontend.ui_auth import login_ui
from agentic_scraper.frontend.ui_auth_credentials import render_credentials_form


def render_sidebar_controls(settings: Settings) -> SidebarConfig:
    """
    Render sidebar controls for login, OpenAI credentials, agent mode, performance, and retries.

    Args:
        settings (Settings): Global settings used to populate default control values.

    Returns:
        SidebarConfig: Parsed sidebar configuration to drive scraper behavior.
    """
    with st.sidebar:
        render_env_and_login(settings)
        selected_agent_mode = render_agent_mode_selector(settings)
        selected_model = render_llm_controls(settings, selected_agent_mode)
        fetch_concurrency, llm_concurrency, verbose, retry_attempts, llm_schema_retries = (
            render_advanced_settings(settings, selected_agent_mode)
        )

    # Persist all values in session
    st.session_state[SESSION_KEYS["screenshot_enabled"]] = st.session_state.get(
        SESSION_KEYS["screenshot_enabled"], settings.screenshot_enabled
    )
    st.session_state[SESSION_KEYS["fetch_concurrency"]] = fetch_concurrency
    st.session_state[SESSION_KEYS["llm_concurrency"]] = llm_concurrency
    st.session_state[SESSION_KEYS["verbose"]] = verbose
    st.session_state[SESSION_KEYS["openai_model"]] = selected_model
    st.session_state[SESSION_KEYS["agent_mode"]] = selected_agent_mode.value
    st.session_state[SESSION_KEYS["retry_attempts"]] = retry_attempts

    return SidebarConfig(
        screenshot_enabled=st.session_state[SESSION_KEYS["screenshot_enabled"]],
        fetch_concurrency=fetch_concurrency,
        llm_concurrency=llm_concurrency,
        verbose=verbose,
        openai_model=selected_model,
        agent_mode=selected_agent_mode.value,
        retry_attempts=retry_attempts,
        llm_schema_retries=llm_schema_retries,
    )


def render_env_and_login(settings: Settings) -> None:
    """
    Display environment information, log path, and authentication UI.

    Args:
        settings (Settings): Global settings to determine current environment and config.
    """
    st.markdown(f"**Environment:** `{get_environment()}`")
    st.markdown(f"**Log Path:** `{get_log_dir() / 'agentic_scraper.log'}`")
    st.markdown("---")

    st.markdown("## 🔐 Authentication")
    login_ui(settings.agent_mode.value)
    if "jwt_token" in st.session_state:
        render_credentials_form()


def render_agent_mode_selector(settings: Settings) -> AgentMode:
    """
    Render the dropdown for selecting agent mode.

    Args:
        settings (Settings): Settings used to determine the default selected mode.

    Returns:
        AgentMode: The selected agent mode (enum value).
    """
    st.markdown("---")
    st.markdown("## 🧠 Agent Mode")
    agent_mode_values = [m.value for m in AgentMode]
    selected_str = st.selectbox(
        "Select Agent Mode",
        options=agent_mode_values,
        index=agent_mode_values.index(settings.agent_mode.value),
        key="agent_mode_select",
        help=(
            "Choose how the agent extracts structured data:\n\n"
            "- llm-fixed: Extracts a fixed set of fields (title, description, price, etc.)\n"
            "- llm-dynamic: Dynamically infers useful fields per page\n"
            "- llm-dynamic-adaptive: Smarter retrying + field prioritization\n"
            "- rule-based: Simple regex-based extraction (no LLM needed)"
        ),
    )
    if selected_str == "rule_based":
        st.session_state["show_auth_overlay"] = False
    else:
        st.session_state["show_auth_overlay"] = True

    return AgentMode(selected_str)


def render_llm_controls(settings: Settings, agent_mode: AgentMode) -> str | None:
    """
    Render the model selection and screenshot toggle controls.

    Args:
        settings (Settings): Settings to determine default model and toggle state.
        agent_mode (AgentMode): Currently selected agent mode.

    Returns:
        str | None: The selected OpenAI model, or None if not applicable.
    """
    selected_model = None
    if agent_mode != AgentMode.RULE_BASED:
        st.markdown("## 🤖 LLM Settings")
        model_keys = list(VALID_MODEL_OPTIONS.keys())
        selected_model = st.selectbox(
            "OpenAI Model",
            options=model_keys,
            index=model_keys.index(settings.openai_model.value),
            format_func=lambda k: VALID_MODEL_OPTIONS[k],
            key="openai_model_select",
            help="Choose which OpenAI model to use for LLM-powered parsing.",
        )

    st.session_state[SESSION_KEYS["screenshot_enabled"]] = st.checkbox(
        "📸 Enable Screenshot",
        value=settings.screenshot_enabled,
    )
    st.markdown("---")
    return selected_model


def render_advanced_settings(
    settings: Settings, agent_mode: AgentMode
) -> tuple[int, int, bool, int, int]:
    """
    Render advanced performance and reliability settings.

    Includes:
    - Concurrency (fetch and/or LLM)
    - Retry attempts
    - LLM schema retries (if using adaptive agent)
    - Verbosity toggle

    Args:
        settings (Settings): App-wide settings providing defaults.
        agent_mode (AgentMode): The current scraping mode selected.

    Returns:
        tuple[int, int, bool, int, int]: A tuple of:
            - fetch_concurrency
            - llm_concurrency
            - verbose
            - retry_attempts
            - llm_schema_retries
    """
    fetch_conc = llm_conc = settings.max_concurrent_requests
    verbose = settings.verbose
    retry_attempts = settings.retry_attempts
    llm_schema_retries = settings.llm_schema_retries

    is_llm_agent = agent_mode != AgentMode.RULE_BASED

    with st.expander("⚙️ Performance Settings (Advanced)", expanded=False):
        st.markdown("### 🔁 Concurrency")

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
            split = False

        if split:
            fetch_conc = st.slider("🌐 Fetch Concurrency", 1, 20, settings.max_concurrent_requests)
            llm_conc = st.slider("🤖 LLM Concurrency", 1, 20, settings.max_concurrent_requests)
        else:
            label = "🔁 Combined Concurrency" if is_llm_agent else "🌐 Fetch Concurrency"
            help_text = (
                "Controls how many tasks run in parallel.\n\n"
                "1. 🌐 Fetching: Limits how many web pages are fetched at the same time.\n"
                "2. 🤖 LLM: Limits how many pages are processed by the AI model at once.\n\n"
                "⚠️ High values may improve speed,\n"
                "   but could hit rate limits or cause instability."
                if is_llm_agent
                else "Controls how many web pages are fetched in parallel."
            )
            concurrency = st.slider(label, 1, 20, settings.max_concurrent_requests, help=help_text)
            fetch_conc = concurrency
            llm_conc = concurrency if is_llm_agent else 0

        st.markdown("### ♻️ Retry Strategy")
        retry_attempts = st.slider("Retry Attempts", 0, 5, settings.retry_attempts)

        placeholder = st.empty()
        if agent_mode == AgentMode.LLM_DYNAMIC_ADAPTIVE:
            with placeholder:
                llm_schema_retries = st.slider(
                    "🧠 LLM Schema Retries",
                    0,
                    5,
                    settings.llm_schema_retries,
                    key=SESSION_KEYS["llm_schema_retries"],
                    help=(
                        "How many times to retry LLM extraction if required fields are missing.\n\n"
                        "🔁 Useful when the AI omits key data (e.g. price, title).\n"
                        "⚠️ Higher values increase latency and token cost."
                    ),
                )
        else:
            placeholder.empty()

        st.markdown("### 📢 Verbosity")
        verbose = st.checkbox(
            "🐞 Verbose error tracebacks",
            value=settings.verbose,
            help=(
                "When enabled, logs the full Python traceback if a scraping task fails.\n\n"
                "✅ Use during development to debug issues.\n"
                "❌ Disable in production for cleaner logs."
            ),
        )

    return fetch_conc, llm_conc, verbose, retry_attempts, llm_schema_retries
