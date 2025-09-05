"""
Authentication helpers for the Streamlit frontend (UI layer).

Responsibilities:
- Render login/logout UI and manage auth-related session state.
- Drive the login flow (incl. pending state + redirect) using Auth0 URLs.
- Fetch user profile and OpenAI-credentials status upon successful token capture.
- Delegate low-level concerns (token parsing, API calls, URL building) to `ui_auth_helpers.py`.

Public API:
- `authenticate_user`: Resolve JWT from URL/session and fetch profile/creds.
- `logout_user`: Clear auth state and refresh UI.
- `login_ui`: Render login/logout controls based on current session state.

Config:
- Pulls settings via `get_settings()` (e.g., verbosity flags).
- Required scopes and SSO URLs are assembled by helper functions.

Operational:
- Network: Low-level calls routed through `ui_auth_helpers` (synchronous `httpx`).
- Logging: Uses message constants; avoids leaking tokens (helpers log masked previews).
- UI: Uses `st.rerun()`/`st.stop()` to ensure clean state transitions.

Usage:
    # Early in your app (e.g., in the sidebar or a top-level layout function):
    authenticate_user()
    login_ui(agent_mode)

Notes:
- This module intentionally contains UI logic only; non-UI auth work (e.g., JWT extraction,
  API base/header construction, and backend fetches) lives in `ui_auth_helpers.py`.
- For agents that do not require authentication (`RULE_BASED`), the login UI is skipped.
"""

from __future__ import annotations

import logging

import streamlit as st

from agentic_scraper.backend.config.messages import (
    MSG_INFO_NO_TOKEN_YET,
    MSG_INFO_TOKEN_SESSION_LENGTH,
    MSG_UI_LOGGED_OUT_APP_ONLY,
    MSG_UI_LOGGING_IN,
)
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.frontend.ui_auth_helpers import (
    build_force_login_url,
    build_login_url,
    build_logout_url,
    fetch_openai_credentials,
    fetch_openai_credentials_status,
    fetch_user_profile,
    get_jwt_token_from_url_or_session,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# -------------------------
# Public entry points
# -------------------------


def authenticate_user() -> None:
    """
    Authenticate the current user and hydrate session state with profile/creds.

    Behavior:
        - If `jwt_token` and `user_info` already exist in `st.session_state`, no-op.
        - Otherwise, attempts to extract a token from the URL (`?token=...`)
          or from session state via `get_jwt_token_from_url_or_session()`.
        - On success, fetches user profile and OpenAI-credentials status (and preview),
          clears `auth_pending`, and triggers a rerun so the UI updates.

    Returns:
        None

    Examples:
        # Call once at the top of your app layout:
        authenticate_user()

    Notes:
        - On 401 responses during fetches, `logout_user()` is invoked to clear state.
        - Uses `st.rerun()` to ensure a consistent UI after state changes.
    """
    # Fast path: already authenticated and user info fetched.
    if "jwt_token" in st.session_state and "user_info" in st.session_state:
        return

    jwt_token = get_jwt_token_from_url_or_session()
    if jwt_token:
        logger.info(MSG_INFO_TOKEN_SESSION_LENGTH.format(length=len(jwt_token)))
        # Fetch profile & creds (logout on 401)
        fetch_user_profile(on_unauthorized=logout_user)
        status = fetch_openai_credentials_status(on_unauthorized=logout_user)
        if status is not None:
            st.session_state["has_openai_credentials"] = bool(status.get("has_credentials"))
            if st.session_state["has_openai_credentials"]:
                fetch_openai_credentials(on_unauthorized=logout_user)
        # Clear pending and refresh the app to reflect new state in the UI.
        st.session_state["auth_pending"] = False
        st.rerun()
    else:
        # No token yet; clear pending state if present.
        logger.info(MSG_INFO_NO_TOKEN_YET)
        st.session_state.pop("auth_pending", None)


def logout_user() -> None:
    """
    Log out from the app by clearing session-held auth data and refreshing the UI.

    Clears:
        - jwt_token, user_info
        - openai_credentials (unmasked), openai_credentials_preview (masked)
        - auth_pending, has_openai_credentials
        - Sets `show_logged_out_banner = True` for a one-time info banner.

    Returns:
        None

    Examples:
        if st.button("Logout"):
            logout_user()

    Notes:
        - This is app-only logout. A separate "global" (SSO) logout link is provided by
          `build_logout_url()` and rendered in `login_ui()`.
    """
    st.session_state.pop("jwt_token", None)
    st.session_state.pop("user_info", None)
    st.session_state.pop("openai_credentials", None)
    st.session_state.pop("openai_credentials_preview", None)
    st.session_state.pop("auth_pending", None)
    st.session_state["show_logged_out_banner"] = True
    st.session_state.pop("has_openai_credentials", None)
    st.rerun()


def login_ui(agent_mode: AgentMode) -> None:
    """
    Render login/logout UI controls in the sidebar according to the session state.

    Behavior:
        - For `AgentMode.RULE_BASED`, no auth is required—UI is skipped.
        - If not authenticated:
            * Show a one-time "logged out" banner when applicable.
            * If an auth flow is pending, show a "Logging in…" message and disable the button.
            * Otherwise, render the primary Auth0 login button and a "force re-auth" link.
        - If authenticated:
            * Show a friendly welcome block (name + email).
            * Offer app-only logout and an SSO-wide logout link (Auth0).

    Args:
        agent_mode (AgentMode): The active agent mode; determines if auth UI is needed.

    Returns:
        None

    Examples:
        with st.sidebar:
            login_ui(agent_mode)

    Notes:
        - The login button issues a meta-refresh to the Auth0 `/authorize` URL. This keeps
          the flow JS-free and works well within Streamlit's model. `st.stop()` is used
          immediately afterward to avoid duplicate rendering in the same frame.
        - Force re-authentication is useful to switch accounts even when SSO is active.
    """
    requires_auth = agent_mode != AgentMode.RULE_BASED
    if not requires_auth:
        return

    with st.sidebar:
        if "jwt_token" not in st.session_state:
            pending = st.session_state.get("auth_pending", False)

            # Show a one-time "logged out" banner after app-only logout.
            if st.session_state.pop("show_logged_out_banner", False):
                st.info(MSG_UI_LOGGED_OUT_APP_ONLY)

            if pending:
                st.info(MSG_UI_LOGGING_IN)
                return

            st.markdown("Click below to log in:")

            # Compose Auth0 authorize URLs (helpers enforce openid/profile/email + HTTPS).
            scope_list = [
                "create:openai_credentials",
                "read:user_profile",
                "create:scrapes",
                "read:scrapes",
                "cancel:scrapes",
            ]
            login_url = build_login_url(scope_list=scope_list)
            force_login_url = build_force_login_url(scope_list=scope_list)

            pending = bool(st.session_state.get("auth_pending"))
            if pending:
                st.info(MSG_UI_LOGGING_IN)  # e.g., "Logging you in…"
                st.button("🔐 Login with Auth0", use_container_width=True, disabled=True)
                # Avoid rendering the force re-auth while a flow is already pending.
                return

            clicked = st.button("🔐 Login with Auth0", use_container_width=True)
            if clicked:
                # Enter pending mode and redirect via meta refresh (same tab, no JS).
                st.session_state["auth_pending"] = True
                st.info(MSG_UI_LOGGING_IN)
                st.markdown(
                    f'<meta http-equiv="refresh" content="0; url={login_url}">',
                    unsafe_allow_html=True,
                )
                # Stop further rendering in this run to prevent double interactions.
                st.stop()

            st.caption(f"Need to switch accounts? [Force re-authentication]({force_login_url}).")

        else:
            user_info = st.session_state.get("user_info", {})
            st.markdown(f"Welcome, **{user_info.get('name', 'User')}**")
            st.markdown(f"📧 Email: `{user_info.get('email', 'N/A')}`")

            if st.button("Logout (this app)"):
                logout_user()

            # Global (SSO) logout via Auth0. This signs out of the upstream IdP when supported.
            logout_url = build_logout_url()
            st.link_button(
                "🌐 Log out everywhere (Auth0)",
                logout_url,
                help="Also sign out of identity provider",
            )
