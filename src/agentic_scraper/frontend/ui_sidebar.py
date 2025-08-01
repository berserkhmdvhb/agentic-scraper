import streamlit as st

from agentic_scraper.backend.config.constants import SESSION_KEYS, VALID_MODEL_OPTIONS
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.frontend.models import SidebarConfig
from agentic_scraper.frontend.ui_auth import login_ui
from agentic_scraper.frontend.ui_auth_credentials import render_credentials_form

def render_sidebar_controls(settings: Settings) -> SidebarConfig:
    """Render sidebar controls for login, OpenAI credentials, and agent settings."""

    with st.sidebar:
        # --- Authentication Section ---
        st.markdown("## 🔐 Authentication")

        agent_mode_values = [m.value for m in AgentMode]
        selected_agent_mode_str = st.selectbox(
            "🧠 Agent Mode",
            options=agent_mode_values,
            index=agent_mode_values.index(settings.agent_mode.value),
            key="agent_mode_select",
            help=(
                "Choose how the agent extracts structured data:\n\n"
                "- `llm-fixed`: Extracts a fixed set of fields (title, description, price, etc.)\n"
                "- `llm-dynamic`: Dynamically infers useful fields per page\n"
                "- `llm-dynamic-adaptive`: Smarter retrying + field prioritization\n"
                "- `rule-based`: Simple regex-based extraction (no LLM needed)"
            ),
        )
        selected_agent_mode = AgentMode(selected_agent_mode_str)

        login_ui(selected_agent_mode.value)

        if "jwt_token" in st.session_state:
            render_credentials_form()
            st.markdown("---")

        # --- LLM Settings ---
        selected_model = None
        if selected_agent_mode != AgentMode.RULE_BASED:
            st.markdown("## 🤖 LLM Settings")
            model_keys = list(VALID_MODEL_OPTIONS.keys())
            selected_model = st.selectbox(
                "OpenAI Model",
                options=model_keys,
                index=model_keys.index(settings.openai_model.value),
                format_func=lambda key: VALID_MODEL_OPTIONS[key],
                key="openai_model_select",
                help="Choose which OpenAI model to use for LLM-powered parsing.",
            )

        screenshot_enabled = st.checkbox(
            "📸 Enable Screenshot", value=settings.screenshot_enabled
        )

        # --- Performance Settings ---
        st.markdown("## ⚙️ Performance Settings")



        with st.expander("🔁 Concurrency Settings", expanded=False):
            is_llm_agent = selected_agent_mode != AgentMode.RULE_BASED

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
                fetch_concurrency = st.slider(
                    "🌐 Fetch Concurrency",
                    min_value=1,
                    max_value=20,
                    value=settings.max_concurrent_requests,
                    help="Max number of web pages fetched in parallel.",
                )
                llm_concurrency = st.slider(
                    "🤖 LLM Concurrency",
                    min_value=1,
                    max_value=20,
                    value=settings.max_concurrent_requests,
                    help="Max number of pages sent to the AI model concurrently.",
                )
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
                concurrency = st.slider(
                    label,
                    min_value=1,
                    max_value=20,
                    value=settings.max_concurrent_requests,
                    help=help_text,
                )
                fetch_concurrency = concurrency
                llm_concurrency = concurrency if is_llm_agent else 0

        verbose = st.checkbox(
            "🐞 Verbose error tracebacks",
            value=settings.verbose,
            help=(
                "When enabled, logs the full Python traceback if a scraping task fails.\n\n"
                "✅ Use during development to debug issues.\n"
                "❌ Disable in production for cleaner logs."
            ),
        )

        retry_attempts = st.slider(
            "♻️ Retry Attempts",
            min_value=0,
            max_value=5,
            value=settings.retry_attempts,
            help="How many times to retry failed fetches or LLM calls. Useful for unstable connections or rate-limited sites.",
        )

        llm_schema_placeholder = st.empty()

        if selected_agent_mode == AgentMode.LLM_DYNAMIC_ADAPTIVE:
            with llm_schema_placeholder:
                llm_schema_retries = st.slider(
                    "🧠 LLM Schema Retries",
                    min_value=0,
                    max_value=5,
                    value=settings.llm_schema_retries,
                    key=SESSION_KEYS["llm_schema_retries"],
                    help=(
                        "How many times to retry LLM extraction if required fields are missing.\n\n"
                        "🔁 Useful when the AI omits key data (e.g. price, title).\n"
                        "⚠️ Higher values increase latency and token cost."
                    ),
                )
        else:
            llm_schema_placeholder.empty()
            llm_schema_retries = st.session_state.get(
                SESSION_KEYS["llm_schema_retries"], settings.llm_schema_retries
            )

    # --- Store in session state ---
    st.session_state[SESSION_KEYS["screenshot_enabled"]] = screenshot_enabled
    st.session_state[SESSION_KEYS["fetch_concurrency"]] = fetch_concurrency
    st.session_state[SESSION_KEYS["llm_concurrency"]] = llm_concurrency
    st.session_state[SESSION_KEYS["verbose"]] = verbose
    st.session_state[SESSION_KEYS["openai_model"]] = selected_model
    st.session_state[SESSION_KEYS["agent_mode"]] = selected_agent_mode.value
    st.session_state[SESSION_KEYS["retry_attempts"]] = retry_attempts
    
    return SidebarConfig(
        screenshot_enabled=screenshot_enabled,
        fetch_concurrency=fetch_concurrency,
        llm_concurrency=llm_concurrency,
        verbose=verbose,
        openai_model=selected_model,
        agent_mode=selected_agent_mode.value,
        retry_attempts=retry_attempts,
        llm_schema_retries=llm_schema_retries,
    )
