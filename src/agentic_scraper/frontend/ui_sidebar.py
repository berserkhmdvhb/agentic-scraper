import streamlit as st

from agentic_scraper.backend.config.constants import VALID_MODEL_OPTIONS
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.frontend.models import SidebarConfig


def render_sidebar_controls(settings: Settings) -> SidebarConfig:
    """Render controls on the sidebar for agent mode, OpenAI model, and performance settings."""
    # --- Agent Mode ---
    agent_mode_values = [m.value for m in AgentMode]
    selected_agent_mode_str = st.sidebar.selectbox(
        "🧠 Agent Mode",
        options=agent_mode_values,
        index=agent_mode_values.index(settings.agent_mode.value),
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
    selected_agent_mode = AgentMode(selected_agent_mode_str)

    # --- OpenAI Model ---
    selected_model = None
    if selected_agent_mode != AgentMode.RULE_BASED:
        model_keys = list(VALID_MODEL_OPTIONS.keys())
        selected_model = st.sidebar.selectbox(
            "🤖 OpenAI Model",
            options=model_keys,
            index=model_keys.index(settings.openai_model.value),
            format_func=lambda key: VALID_MODEL_OPTIONS[key],
            key="openai_model_select",
            help="Choose which OpenAI model to use for LLM-powered parsing.",
        )

    screenshot_enabled = st.sidebar.checkbox(
        "📸 Enable Screenshot", value=settings.screenshot_enabled
    )

    # Performance & retry settings
    retry_attempts = st.sidebar.slider(
        "♻️ Retry Attempts", min_value=0, max_value=5, value=settings.retry_attempts
    )

    # Return the configuration as a model
    return SidebarConfig(
        screenshot_enabled=screenshot_enabled,
        fetch_concurrency=settings.fetch_concurrency,
        llm_concurrency=settings.llm_concurrency,
        verbose=settings.verbose,
        openai_model=selected_model,
        agent_mode=selected_agent_mode.value,
        retry_attempts=retry_attempts,
        llm_schema_retries=settings.llm_schema_retries,
    )
