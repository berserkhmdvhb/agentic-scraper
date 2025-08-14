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

from __future__ import annotations

import streamlit as st

from agentic_scraper.backend.config.constants import SESSION_KEYS, VALID_MODEL_OPTIONS
from agentic_scraper.backend.config.types import AgentMode, OpenAIModel
from agentic_scraper.backend.core.settings import Settings, get_environment, get_log_dir
from agentic_scraper.frontend.models import SidebarConfig
from agentic_scraper.frontend.ui_auth import login_ui
from agentic_scraper.frontend.ui_auth_credentials import render_credentials_form

# -------------------------
# Public API
# -------------------------


def render_sidebar_controls(settings: Settings) -> SidebarConfig:
    """
    Render sidebar controls for login, OpenAI credentials, agent mode, performance, and retries.

    Args:
        settings: Global settings used to populate default control values.

    Returns:
        SidebarConfig: Parsed sidebar configuration to drive scraper behavior.
    """
    with st.sidebar:
        # 1) Agent mode first so downstream sections know whether auth is required
        selected_agent_mode = _render_agent_mode_selector(settings)

        # 2) Environment + login (uses selected agent mode)
        _render_env_and_login(settings, selected_agent_mode)

        # 3) LLM model + screenshot toggle
        selected_model = _render_llm_controls(settings, selected_agent_mode)

        # 4) Advanced performance/retry settings
        (
            fetch_concurrency,
            llm_concurrency,
            verbose,
            retry_attempts,
            llm_schema_retries,
        ) = _render_advanced_settings(settings, selected_agent_mode)

    # Persist values in session (single source of truth for the rest of the app)
    st.session_state[SESSION_KEYS["screenshot_enabled"]] = st.session_state.get(
        SESSION_KEYS["screenshot_enabled"], settings.screenshot_enabled
    )
    st.session_state[SESSION_KEYS["fetch_concurrency"]] = fetch_concurrency
    st.session_state[SESSION_KEYS["llm_concurrency"]] = llm_concurrency
    st.session_state[SESSION_KEYS["verbose"]] = verbose
    st.session_state[SESSION_KEYS["openai_model"]] = selected_model
    st.session_state[SESSION_KEYS["agent_mode"]] = selected_agent_mode
    st.session_state[SESSION_KEYS["retry_attempts"]] = retry_attempts

    return SidebarConfig(
        screenshot_enabled=st.session_state[SESSION_KEYS["screenshot_enabled"]],
        fetch_concurrency=fetch_concurrency,
        llm_concurrency=llm_concurrency,
        verbose=verbose,
        openai_model=selected_model,
        agent_mode=selected_agent_mode,
        retry_attempts=retry_attempts,
        llm_schema_retries=llm_schema_retries,
    )


# -------------------------
# Sections
# -------------------------


def _render_env_and_login(settings: Settings, agent_mode: AgentMode) -> None:
    """Display environment info, log path, and authentication UI (if needed)."""
    st.markdown(f"**Environment:** `{get_environment()}`")
    st.markdown(f"**Log Path:** `{get_log_dir() / 'agentic_scraper.log'}`")
    # Optionally surface domains if available in settings
    if getattr(settings, "frontend_domain", None):
        st.markdown(f"**Frontend:** `{settings.frontend_domain}`")
    if getattr(settings, "backend_domain", None):
        st.markdown(f"**Backend:** `{settings.backend_domain}`")
    st.markdown("---")

    st.markdown("## 🔐 Authentication")
    login_ui(agent_mode)
    if agent_mode != AgentMode.RULE_BASED and "jwt_token" in st.session_state:
        # Only show credential form for LLM modes when logged in
        render_credentials_form()


def _render_agent_mode_selector(settings: Settings) -> AgentMode:
    """Render the dropdown for selecting agent mode and drive auth overlay state."""
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

    # Toggle overlay for auth guidance outside the sidebar
    st.session_state["show_auth_overlay"] = selected_str != AgentMode.RULE_BASED.value

    return AgentMode(selected_str)


def _render_llm_controls(settings: Settings, agent_mode: AgentMode) -> OpenAIModel | None:
    """Render model selection (LLM modes) and the screenshot toggle."""
    selected_model: OpenAIModel | None = None

    if agent_mode != AgentMode.RULE_BASED:
        st.markdown("## 🤖 LLM Settings")
        model_keys = list(VALID_MODEL_OPTIONS.keys())
        # Fall back safely if current default not in VALID_MODEL_OPTIONS
        model_value = settings.openai_model.value
        default_model_key = model_value if model_value in model_keys else model_keys[0]
        selected_key = st.selectbox(
            "OpenAI Model",
            options=model_keys,
            index=model_keys.index(default_model_key),
            format_func=lambda k: VALID_MODEL_OPTIONS[k],
            key="openai_model_select",
            help="Choose which OpenAI model to use for LLM-powered parsing.",
        )
        selected_model = OpenAIModel(selected_key)
    # Screenshot toggle (applies to all modes)
    st.session_state[SESSION_KEYS["screenshot_enabled"]] = st.checkbox(
        "📸 Enable Screenshot",
        value=st.session_state.get(SESSION_KEYS["screenshot_enabled"], settings.screenshot_enabled),
    )

    st.markdown("---")
    return selected_model


def _render_advanced_settings(
    settings: Settings, agent_mode: AgentMode
) -> tuple[int, int, bool, int, int]:
    """
    Render advanced performance and reliability settings.

    Returns a tuple of:
      (fetch_concurrency, llm_concurrency, verbose, retry_attempts, llm_schema_retries)
    """
    # Defaults
    fetch_conc = getattr(settings, "max_concurrent_requests", 5)
    llm_conc = fetch_conc
    verbose = getattr(settings, "verbose", False)
    retry_attempts = getattr(settings, "retry_attempts", 1)
    llm_schema_retries = getattr(settings, "llm_schema_retries", 1)

    is_llm_agent = agent_mode != AgentMode.RULE_BASED

    with st.expander("⚙️ Performance Settings (Advanced)", expanded=False):
        st.markdown("### 🔁 Concurrency")

        split = is_llm_agent and st.checkbox(
            "🔧 Separate fetch and LLM controls",
            help=(
                "Enable this to control fetch and LLM concurrency separately.\n\n"
                "Useful if:\n"
                "• You want to fetch many pages but limit OpenAI load.\n"
                "• You're tuning for different I/O vs compute bottlenecks."
            ),
        )

        if split:
            fetch_conc = st.slider("🌐 Fetch Concurrency", 1, 20, int(fetch_conc))
            llm_conc = st.slider("🤖 LLM Concurrency", 1, 20, int(llm_conc))
        else:
            label = "🔁 Combined Concurrency" if is_llm_agent else "🌐 Fetch Concurrency"
            help_text = (
                "Controls how many tasks run in parallel.\n\n"
                "1. 🌐 Fetching: Limits how many web pages are fetched at the same time.\n"
                "2. 🤖 LLM: Limits how many pages are processed by the AI model at once.\n\n"
                "⚠️ High values may improve speed, but could hit rate limits or cause instability."
                if is_llm_agent
                else "Controls how many web pages are fetched in parallel."
            )
            concurrency = st.slider(label, 1, 20, int(fetch_conc), help=help_text)
            fetch_conc = concurrency
            llm_conc = concurrency if is_llm_agent else 0

        st.markdown("### ♻️ Retry Strategy")
        retry_attempts = st.slider("Retry Attempts", 0, 5, int(retry_attempts))

        placeholder = st.empty()
        if agent_mode == AgentMode.LLM_DYNAMIC_ADAPTIVE:
            with placeholder:
                llm_schema_retries = st.slider(
                    "🧠 LLM Schema Retries",
                    0,
                    5,
                    int(llm_schema_retries),
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
            value=bool(verbose),
            help=(
                "When enabled, logs the full Python traceback if a scraping task fails.\n\n"
                "✅ Use during development to debug issues.\n"
                "❌ Disable in production for cleaner logs."
            ),
        )

    return (
        int(fetch_conc),
        int(llm_conc),
        bool(verbose),
        int(retry_attempts),
        int(llm_schema_retries),
    )
