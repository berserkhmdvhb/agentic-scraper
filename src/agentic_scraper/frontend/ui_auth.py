"""
Authentication helpers for the Streamlit frontend (UI layer).

This module focuses on the UI flow and delegates low-level tasks to
`ui_auth_helpers.py`, including:
- Parsing JWT tokens from URL/session
- Building API base URLs and headers
- Fetching user profile and OpenAI credentials

It renders the Auth0 login button, triggers authentication, and exposes
logout controls. Non-UI details live in `ui_auth_helpers.py`.
"""

from __future__ import annotations

import logging
import urllib.parse

import streamlit as st

from agentic_scraper.backend.config.messages import (
    MSG_INFO_AUTH0_LOGIN_URI,
    MSG_INFO_NO_TOKEN_YET,
    MSG_INFO_TOKEN_SESSION_LENGTH,
    MSG_UI_LOGGED_OUT_APP_ONLY,
    MSG_UI_LOGGING_IN,
)
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.frontend.ui_auth_helpers import (
    ensure_https,
    fetch_openai_credentials,
    fetch_user_profile,
    get_jwt_token_from_url_or_session,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# -------------------------
# Public entry points
# -------------------------


def authenticate_user() -> None:
    """Authenticate user by extracting JWT, then fetching profile + credentials."""
    if "jwt_token" in st.session_state and "user_info" in st.session_state:
        return

    jwt_token = get_jwt_token_from_url_or_session()
    if jwt_token:
        logger.info(MSG_INFO_TOKEN_SESSION_LENGTH.format(length=len(jwt_token)))
        # Fetch profile & creds (logout on 401)
        fetch_user_profile(on_unauthorized=logout_user)
        fetch_openai_credentials(on_unauthorized=logout_user)
        st.session_state["auth_pending"] = False
        st.rerun()
    else:
        logger.info(MSG_INFO_NO_TOKEN_YET)
        st.session_state.pop("auth_pending", None)


def logout_user() -> None:
    """Clear authentication-related session data and refresh UI."""
    st.session_state.pop("jwt_token", None)
    st.session_state.pop("user_info", None)
    st.session_state.pop("openai_credentials", None)
    st.session_state.pop("openai_credentials_preview", None)
    st.session_state.pop("auth_pending", None)
    st.session_state["show_logged_out_banner"] = True
    st.rerun()


def login_ui(agent_mode: AgentMode) -> None:
    """Render login or logout UI components based on current session state."""
    requires_auth = agent_mode != AgentMode.RULE_BASED

    if not requires_auth:
        return

    with st.sidebar:
        if "jwt_token" not in st.session_state:
            pending = st.session_state.get("auth_pending", False)
            if st.session_state.pop("show_logged_out_banner", False):
                st.info(MSG_UI_LOGGED_OUT_APP_ONLY)
            if pending:
                st.info(MSG_UI_LOGGING_IN)
                return
            st.markdown("Click below to log in:")

            # Auth0 authorize URL (scopes include scrapes & user/creds)
            audience = settings.auth0_api_audience  # already configured with trailing '/'
            redirect_uri = ensure_https(settings.auth0_redirect_uri)
            domain = settings.auth0_domain
            client_id = settings.auth0_client_id

            scope_list = [
                "openid",
                "profile",
                "email",
                "create:openai_credentials",
                "read:user_profile",
                "create:scrapes",
                "read:scrapes",
                "cancel:scrapes",
            ]
            scope = " ".join(scope_list)

            # Build query safely
            query = urllib.parse.urlencode(
                {
                    "client_id": client_id,
                    "response_type": "code",
                    "redirect_uri": redirect_uri,
                    "audience": audience,
                    "scope": scope,
                }
            )
            login_url = f"https://{domain}/authorize?{query}"

            if settings.is_verbose_mode:
                logger.debug(MSG_INFO_AUTH0_LOGIN_URI.format(uri=login_url))

            st.markdown(
                f"""
                <div class="auth-highlight">
                    <a href="{login_url}" target="_self">
                        <button style="
                            width: 100%;
                            padding: 0.5rem 1rem;
                            border-radius: 0.5rem;
                            background-color: #EF476F;
                            color: white;
                            font-weight: bold;
                            border: none;
                            cursor: pointer;
                        ">
                            🔐 Login with Auth0
                        </button>
                    </a>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            user_info = st.session_state.get("user_info", {})
            st.markdown(f"Welcome, **{user_info.get('name', 'User')}**")
            st.markdown(f"📧 Email: `{user_info.get('email', 'N/A')}`")

            if st.button("Logout"):
                logout_user()
