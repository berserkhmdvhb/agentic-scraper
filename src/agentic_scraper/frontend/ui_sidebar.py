"""
Sidebar controls for the Streamlit frontend of AgenticScraper.

Responsibilities:
- Render environment info and authentication controls.
- Collect OpenAI credentials (when authenticated and using LLM agents).
- Select agent mode and LLM model; toggle screenshots.
- Configure advanced performance settings (concurrency, retries, verbosity).
- Offer presets for quick, sensible configurations.

Public API:
- `render_sidebar_controls`: Render the full sidebar and return a `SidebarConfig`.

Config:
- Reads defaults from `Settings` (e.g., `agent_mode`, `openai_model`,
  `screenshot_enabled`, `max_concurrent_requests`, retry settings).
- Uses constants from `backend.config.constants` (session keys, model options, thresholds).

Operational:
- Streamlit-only UI; persists selections in `st.session_state` for downstream use.
- Avoids behavior changes by only adding docstrings and clarifying comments.

Usage:
    from agentic_scraper.frontend.ui_sidebar import render_sidebar_controls
    config = render_sidebar_controls(settings)

Notes:
- The sidebar writes authoritative values into `st.session_state[...]` keys defined
  by `SESSION_KEYS` so other pages (e.g., Jobs tab) can reference them reliably.
- LLM-specific controls are hidden for `RULE_BASED` mode, but a valid `OpenAIModel`
  is still returned for downstream logic that expects a value.
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

__all__ = ["render_sidebar_controls"]  # public surface for this module


# -------------------------
# Module constants
# -------------------------
class PresetControls(NamedTuple):
    """
    Small container for live control values used to detect preset divergence.

    Attributes:
        fetch_conc (int): Current fetch concurrency.
        llm_conc (int): Current LLM concurrency.
        verbose (bool): Verbose logging toggle.
        retry_attempts (int): Overall retry attempts.
        llm_schema_retries (int): Schema retries for adaptive LLM agents.
    """

    fetch_conc: int
    llm_conc: int
    verbose: bool
    retry_attempts: int
    llm_schema_retries: int


# -------------------------
# Presets
# -------------------------
class Preset(TypedDict):
    """
    A preset defines a coherent set of sidebar control values.

    Keys:
        fetch_concurrency (int): Network concurrency.
        llm_concurrency (int | None): LLM concurrency, or None → match fetch.
        verbose (bool): Verbose logging.
        retry_attempts (int): Retry attempts for failures.
        llm_schema_retries (int): Schema retries for adaptive LLM agents.
        screenshot_enabled (bool): Screenshot capture toggle.
    """

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
    Render sidebar controls for login/auth, credentials, agent mode, model, and performance.

    Args:
        settings (Settings): Global settings used to seed default control values.

    Returns:
        SidebarConfig: Parsed sidebar configuration to drive scraper behavior.

    Notes:
        - Persists authoritative values to `st.session_state[SESSION_KEYS[...]]`
          so other views (e.g., Jobs tab) can consume them without re-opening the sidebar.
        - LLM schema retries are always set in session to ensure a defined value even when hidden.
    """
    with st.sidebar:
        _render_header_chip_row(settings)

        # Theme tip (Streamlit has a built-in theme switch under ••• menu → Settings)
        st.caption("Theme: use ••• → Settings → Theme (Light/Dark/System).")

        st.divider()

        # 1) Authentication & Environment details (credentials shown only for LLM modes)
        _render_auth_and_env(
            AgentMode(st.session_state.get("agent_mode_select", settings.agent_mode.value))
        )

        # 2) Agent Mode
        selected_agent_mode = _render_agent_mode_selector(settings)

        # 3) LLM model + screenshot toggle (paired with Agent Mode)
        selected_model = _render_llm_controls(settings, selected_agent_mode)

        # 4) Advanced (closed expander by default)
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
    # even when the control is hidden (non-adaptive agents).
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
    Show compact chips for Auth, Environment, and quick links.

    Displays:
        - Auth state (✅/❌)
        - Environment name (e.g., "local", "prod")
        - An expander with log path, frontend, and backend URLs

    Notes:
        - We cache environment + log dir to avoid repeated filesystem calls.
        - Mirrors environment details into `st.session_state` so other pages can read them.
    """

    @st.cache_resource
    def _env_info() -> tuple[str, Path]:
        return get_environment(), get_log_dir()

    env, _log_dir = _env_info()
    authed = "jwt_token" in st.session_state

    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown(f"**🔐 Auth:** {'✅' if authed else '❌'}")
    with c2:
        st.markdown(f"**🌐 Env:** `{env}`")

    with st.expander("Environment Details", expanded=False):
        env, log_dir = _env_info()
        st.markdown(f"**Environment:** `{env}`")
        st.markdown(f"**Log Path:** `{(log_dir / 'agentic_scraper.log')}`")
        if getattr(settings, "frontend_domain", None):
            st.markdown(f"**Frontend:** [{settings.frontend_domain}]({settings.frontend_domain})")
        if getattr(settings, "backend_domain", None):
            st.markdown(f"**Backend:** [{settings.backend_domain}]({settings.backend_domain})")

    # Make sure Jobs tab can read these even if the sidebar wasn't opened again.
    st.session_state.setdefault("environment", env)
    if getattr(settings, "frontend_domain", None):
        st.session_state["frontend_domain"] = settings.frontend_domain
    if getattr(settings, "backend_domain", None):
        st.session_state["backend_domain"] = settings.backend_domain


def _render_auth_and_env(agent_mode: AgentMode) -> None:
    """
    Render authentication UI and (conditional) OpenAI credentials form.

    Args:
        agent_mode (AgentMode): Active mode—LLM modes show the credentials form.

    Returns:
        None
    """
    st.subheader("Authentication", anchor=False)
    login_ui(agent_mode)

    # Only show the credentials form when authenticated and LLM is required.
    if agent_mode != AgentMode.RULE_BASED and "jwt_token" in st.session_state:
        render_credentials_form()


def _render_agent_mode_selector(settings: Settings) -> AgentMode:
    """
    Render the Agent Mode selector with concise help text.

    Args:
        settings (Settings): Global defaults (used to select initial agent mode).

    Returns:
        AgentMode: The user-selected agent mode.

    Notes:
        - Sets `st.session_state["show_auth_overlay"]` to guide the main pane
          about whether to display an auth overlay (non-rule modes need auth).
    """
    st.divider()
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
    """
    Render a minimal preset selector.

    Returns:
        str: Selected preset name (or "Custom" when diverged).

    Notes:
        - Currently used as a lightweight hook; selection is compared
          via `_compute_effective_preset` when controls change.
    """
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

    Ensures an `OpenAIModel` is always returned (uses settings default if hidden).

    Args:
        settings (Settings): Defaults for model and screenshot.
        agent_mode (AgentMode): Determines whether to show model selection.

    Returns:
        OpenAIModel: The selected (or default) LLM model.
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

    # Screenshot toggle (applies to all modes); simple defaulting (no presets).
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
        tuple[int, int, bool, int, int]:
            (fetch_concurrency, llm_concurrency, verbose, retry_attempts, llm_schema_retries)

    Notes:
        - When not in an LLM mode, the combined slider controls only fetch concurrency,
          and LLM concurrency is fixed to 0 to reflect its irrelevance.
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
    """
    Compute whether the current controls still match the selected preset.

    Returns:
        str: The effective preset, or "Custom" if controls diverged.

    Notes:
        - Divergence includes screenshot toggle differences and any control value drift.
    """
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
    """
    Compact jobs/status handoff at the bottom of the sidebar.

    Notes:
        - Shows the last job id + status if available, with a hint to open the Jobs tab.
        - Keeps the sidebar minimal; the Jobs tab owns monitoring UX.
    """
    last_job_id = st.session_state.get("last_job_id")
    last_job_status = st.session_state.get("last_job_status")

    if last_job_id and last_job_status:
        st.markdown(f"**Last Job:** `{last_job_status}` · `{last_job_id}`")

    # If your app uses tabs or query params, a simple hint helps users orient.
    st.caption("Open the Jobs tab to monitor progress and history.")
