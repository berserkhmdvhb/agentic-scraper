"""
Sidebar controls for the Streamlit frontend of AgenticScraper.

This module renders the interactive sidebar UI for:
- Environment display and login/authentication
- OpenAI credentials input (conditional on login)
- Agent mode selection
- Model selection and screenshot toggle
- Advanced settings for concurrency, retries, and verbosity
- Optional presets to quickly configure a sensible setup

Returns a `SidebarConfig` object with user-selected values to control scraping behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, TypedDict

import streamlit as st

from agentic_scraper.backend.config.constants import (
    SESSION_KEYS,
    URL_NUDGE_THRESHOLD,
    VALID_MODEL_OPTIONS,
)
from agentic_scraper.backend.config.types import AgentMode, OpenAIModel
from agentic_scraper.backend.core.settings import Settings, get_environment, get_log_dir
from agentic_scraper.frontend.models import SidebarConfig
from agentic_scraper.frontend.ui_auth import login_ui
from agentic_scraper.frontend.ui_auth_credentials import render_credentials_form


# -------------------------
# Module constants
# -------------------------
class PresetControls(NamedTuple):
    fetch_conc: int
    llm_conc: int
    verbose: bool
    retry_attempts: int
    llm_schema_retries: int


# -------------------------
# Presets
# -------------------------


class Preset(TypedDict):
    fetch_concurrency: int
    llm_concurrency: int | None  # None means "match fetch_concurrency"
    verbose: bool
    retry_attempts: int
    llm_schema_retries: int
    screenshot_enabled: bool


PRESETS: dict[str, Preset] = {
    "Balanced": {
        "fetch_concurrency": 5,
        "llm_concurrency": None,
        "verbose": False,
        "retry_attempts": 1,
        "llm_schema_retries": 1,
        "screenshot_enabled": False,
    },
    "Fast": {
        "fetch_concurrency": 10,
        "llm_concurrency": None,
        "verbose": False,
        "retry_attempts": 0,
        "llm_schema_retries": 0,
        "screenshot_enabled": False,
    },
    "Quality": {
        "fetch_concurrency": 4,
        "llm_concurrency": 2,
        "verbose": False,
        "retry_attempts": 2,
        "llm_schema_retries": 2,
        "screenshot_enabled": True,
    },
    "Adaptive+": {
        "fetch_concurrency": 6,
        "llm_concurrency": 3,
        "verbose": False,
        "retry_attempts": 2,
        "llm_schema_retries": 3,
        "screenshot_enabled": False,
    },
    # "Custom" will be computed when user diverges from preset values
}


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
        _render_header_chip_row(settings)

        # Theme tip (built-in Streamlit theme switch lives in ••• menu → Settings)
        st.caption("Theme: use ••• → Settings → Theme (Light/Dark/System).")

        st.divider()

        # 1) Agent Mode
        selected_agent_mode = _render_agent_mode_selector(settings)

        # 2) Authentication & Environment details (credentials shown only for LLM modes)
        _render_auth_and_env(selected_agent_mode)

        # 3) LLM model + screenshot toggle (no presets involved)
        selected_model = _render_llm_controls(settings, selected_agent_mode)

        # 4) Advanced (now in a closed expander by default)
        (
            fetch_concurrency,
            llm_concurrency,
            verbose,
            retry_attempts,
            llm_schema_retries,
        ) = _render_advanced_settings(settings, selected_agent_mode)

        # 5) Jobs / status entry point (compact)
        _render_jobs_footer()

    # Persist values in session (single source of truth for the rest of the app)
    st.session_state[SESSION_KEYS["screenshot_enabled"]] = st.session_state.get(
        SESSION_KEYS["screenshot_enabled"], settings.screenshot_enabled
    )
    st.session_state[SESSION_KEYS["fetch_concurrency"]] = int(fetch_concurrency)
    st.session_state[SESSION_KEYS["llm_concurrency"]] = int(llm_concurrency)
    st.session_state[SESSION_KEYS["verbose"]] = bool(verbose)
    st.session_state[SESSION_KEYS["openai_model"]] = selected_model
    st.session_state[SESSION_KEYS["agent_mode"]] = selected_agent_mode
    st.session_state[SESSION_KEYS["retry_attempts"]] = int(retry_attempts)

    # Always set llm_schema_retries in session to a safe int value,
    # even when not in Adaptive mode, to avoid downstream "missing key" issues.
    st.session_state[SESSION_KEYS["llm_schema_retries"]] = int(llm_schema_retries)

    return SidebarConfig(
        screenshot_enabled=bool(st.session_state[SESSION_KEYS["screenshot_enabled"]]),
        fetch_concurrency=int(fetch_concurrency),
        llm_concurrency=int(llm_concurrency),
        verbose=bool(verbose),
        openai_model=selected_model,
        agent_mode=selected_agent_mode,
        retry_attempts=int(retry_attempts),
        llm_schema_retries=int(llm_schema_retries),
    )


# -------------------------
# Sections
# -------------------------


def _render_header_chip_row(settings: Settings) -> None:
    """
    Show compact chips for Auth, Environment, and a quick link area.
    Full details are in an expander below.
    """

    @st.cache_resource
    def _env_info() -> tuple[str, Path]:
        return get_environment(), get_log_dir()

    env, _log_dir = _env_info()
    authed = "jwt_token" in st.session_state

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.markdown(f"**🔐 Auth:** {'✅' if authed else '❌'}")
    with c2:
        st.markdown(f"**🌐 Env:** `{env}`")
    with c3:
        # Placeholder for quick action, e.g., docs or Swagger link if you have it.
        # Keep minimal to avoid coupling.
        st.markdown("**📄 Logs:** `…`")

    with st.expander("Environment Details", expanded=False):
        env, log_dir = _env_info()
        st.markdown(f"**Environment:** `{env}`")
        st.markdown(f"**Log Path:** `{(log_dir / 'agentic_scraper.log')}`")
        if getattr(settings, "frontend_domain", None):
            st.markdown(f"**Frontend:** `{settings.frontend_domain}`")
        if getattr(settings, "backend_domain", None):
            st.markdown(f"**Backend:** `{settings.backend_domain}`")


def _render_auth_and_env(agent_mode: AgentMode) -> None:
    """Authentication UI and (conditional) OpenAI credentials form."""
    st.subheader("Authentication", anchor=False)
    login_ui(agent_mode)

    if agent_mode != AgentMode.RULE_BASED and "jwt_token" in st.session_state:
        render_credentials_form()


def _render_agent_mode_selector(settings: Settings) -> AgentMode:
    """Agent Mode selection with concise help and an auth overlay toggle."""
    st.subheader("🧠 Agent Mode", anchor=False)

    agent_mode_values = [m.value for m in AgentMode]
    default_index = (
        agent_mode_values.index(settings.agent_mode.value)
        if settings.agent_mode.value in agent_mode_values
        else 0
    )

    selected_str = st.selectbox(
        "Select Agent Mode",
        options=agent_mode_values,
        index=default_index,
        key="agent_mode_select",
        help=(
            "How to extract structured data:\n"
            "• llm-fixed → Fixed fields (title, desc, price)\n"
            "• llm-dynamic → Infers useful fields per page\n"
            "• llm-dynamic-adaptive → Smarter retries & prioritization\n"
            "• rule-based → Regex/no-LLM\n"
        ),
    )

    # Toggle overlay for auth guidance outside the sidebar
    st.session_state["show_auth_overlay"] = selected_str != AgentMode.RULE_BASED.value

    return AgentMode(selected_str)


def _render_preset_selector() -> str:
    """Render a small Preset selector. Returns the selected preset name (or 'Custom')."""
    st.subheader("Run Preset", anchor=False)

    # Initialize preset in session once
    default_preset = st.session_state.get("ui_sidebar_preset", "Balanced")
    options = ["Balanced", "Fast", "Quality", "Adaptive+", "Custom"]

    return st.selectbox(
        "Preset",
        options=options,
        index=options.index(default_preset) if default_preset in options else 0,
        help=(
            "Quickly apply a sensible combination of concurrency, retries, and screenshots.\n"
            "Switches to 'Custom' when you tweak settings."
        ),
        key="ui_sidebar_preset_select",
    )


def _render_llm_controls(
    settings: Settings,
    agent_mode: AgentMode,
) -> OpenAIModel:
    """
    Render model selection for LLM modes and the Screenshot toggle for all modes.
    Ensures an OpenAIModel is always returned (uses settings default if hidden).
    """
    # Determine URL count if available to nudge screenshot choice (optional)
    url_count = int(st.session_state.get("url_count", 0))

    selected_model: OpenAIModel

    if agent_mode != AgentMode.RULE_BASED:
        st.subheader("LLM Settings", anchor=False)

        model_keys = list(VALID_MODEL_OPTIONS.keys())
        if not model_keys:
            # Fallback to settings in the unlikely case there are no options configured
            selected_model = settings.openai_model
            st.info("No model options configured; using default from settings.")
        else:
            model_value = settings.openai_model.value
            default_model_key = model_value if model_value in model_keys else model_keys[0]
            selected_key = st.selectbox(
                "OpenAI Model",
                options=model_keys,
                index=model_keys.index(default_model_key),
                format_func=lambda k: VALID_MODEL_OPTIONS[k],
                key="openai_model_select",
                help="Model used for LLM-powered parsing.",
            )
            selected_model = OpenAIModel(selected_key)
    else:
        # Rule-based mode does not expose a model picker; keep a valid value for downstream logic.
        selected_model = settings.openai_model

    # Screenshot toggle (applies to all modes); simple defaulting (no presets)
    initial_value = st.session_state.get(
        SESSION_KEYS["screenshot_enabled"], settings.screenshot_enabled
    )
    screenshot_enabled = st.checkbox(
        "📸 Enable Screenshot",
        value=bool(initial_value),
        help="Captures page screenshots for each item (adds I/O and latency).",
    )
    st.session_state[SESSION_KEYS["screenshot_enabled"]] = bool(screenshot_enabled)

    # Nudge for large batches
    if url_count >= URL_NUDGE_THRESHOLD and screenshot_enabled:
        st.caption("Tip: For large batches, consider turning screenshots off for speed.")

    st.divider()
    return selected_model


def _render_advanced_settings(
    settings: Settings,
    agent_mode: AgentMode,
) -> tuple[int, int, bool, int, int]:
    """
    Render advanced performance and reliability settings inside a closed expander.

    Returns:
        (fetch_concurrency, llm_concurrency, verbose, retry_attempts, llm_schema_retries)
    """
    is_llm_agent = agent_mode != AgentMode.RULE_BASED

    # Base defaults from settings
    fetch_default = int(getattr(settings, "max_concurrent_requests", 5))
    llm_default = int(fetch_default)
    verbose_default = bool(getattr(settings, "verbose", False))
    retry_default = int(getattr(settings, "retry_attempts", 1))
    schema_retry_default = int(getattr(settings, "llm_schema_retries", 1))

    fetch_conc = fetch_default
    llm_conc = llm_default if is_llm_agent else 0
    verbose = verbose_default
    retry_attempts = retry_default
    llm_schema_retries = schema_retry_default

    with st.expander("⚙️ Performance Settings (Advanced)", expanded=False):
        # Remember user's preference for split vs combined
        split_key = "ui_sidebar_split_concurrency"
        split_default = bool(st.session_state.get(split_key, False))

        st.markdown("🔁 **Concurrency**")
        split = is_llm_agent and st.checkbox(
            "Separate Fetch and LLM Controls",
            value=split_default,
            help="Tune network fetch and model processing separately.",
            key=split_key,
        )

        # Sliders (with units in labels)
        if split and is_llm_agent:
            fetch_conc = st.slider("🌐 Fetch Concurrency (requests)", 1, 20, int(fetch_default))
            llm_conc = st.slider("🤖 LLM Concurrency (requests)", 1, 20, int(llm_default))
        else:
            label = (
                "🔁 Combined Concurrency (requests)"
                if is_llm_agent
                else "🌐 Fetch Concurrency (requests)"
            )
            combined = st.slider(label, 1, 20, int(fetch_default))
            fetch_conc = combined
            llm_conc = combined if is_llm_agent else 0

        st.markdown("♻️ **Retry Strategy**")
        retry_attempts = st.slider("Retry Attempts", 0, 5, int(retry_default))

        # Adaptive-only schema retries; always keep a safe session value
        placeholder = st.empty()
        if agent_mode == AgentMode.LLM_DYNAMIC_ADAPTIVE:
            with placeholder:
                llm_schema_retries = st.slider(
                    "🧠 LLM Schema Retries",
                    0,
                    5,
                    int(schema_retry_default),
                    key=SESSION_KEYS["llm_schema_retries"],
                    help=(
                        "Extra attempts if required fields are missing. "
                        "Increases latency and token cost."
                    ),
                )
        else:
            placeholder.empty()

        st.markdown("**Verbosity**")
        verbose = st.checkbox(
            "🐞 Verbose Error Tracebacks",
            value=bool(verbose_default),
            help="Enable for debugging; disable for cleaner logs.",
        )

    return (
        int(fetch_conc),
        int(llm_conc),
        bool(verbose),
        int(retry_attempts),
        int(llm_schema_retries),
    )


def _compute_effective_preset(
    selected_preset: str,
    controls: PresetControls,
) -> str:
    """Return 'Custom' if current controls diverge from the selected preset."""
    if selected_preset == "Custom":
        return "Custom"

    preset = PRESETS.get(selected_preset, PRESETS["Balanced"])
    target_fetch = preset["fetch_concurrency"]
    target_llm = (
        preset["llm_concurrency"] if preset["llm_concurrency"] is not None else target_fetch
    )
    target_verbose = preset["verbose"]
    target_retry = preset["retry_attempts"]
    target_schema = preset["llm_schema_retries"]

    diverged = any(
        [
            int(controls.fetch_conc) != int(target_fetch),
            int(controls.llm_conc) != int(target_llm),
            bool(controls.verbose) != bool(target_verbose),
            int(controls.retry_attempts) != int(target_retry),
            int(controls.llm_schema_retries) != int(target_schema),
            bool(st.session_state.get(SESSION_KEYS["screenshot_enabled"], False))
            != bool(preset["screenshot_enabled"]),
        ]
    )
    return "Custom" if diverged else selected_preset


def _render_jobs_footer() -> None:
    """Compact jobs/status handoff at the bottom of the sidebar."""
    last_job_id = st.session_state.get("last_job_id")
    last_job_status = st.session_state.get("last_job_status")

    if last_job_id and last_job_status:
        st.markdown(f"**Last Job:** `{last_job_status}` · `{last_job_id}`")

    # If your app uses tabs or query params, a simple hint helps users orient.
    st.caption("Open the Jobs tab to monitor progress and history.")
