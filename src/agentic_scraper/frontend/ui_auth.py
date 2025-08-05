"""
Authentication helpers for the Streamlit frontend.

This module handles:
- Parsing JWT tokens from query parameters or session state
- Authenticating users via Auth0 and populating session state
- Fetching user profile and OpenAI credentials from the backend
- Rendering login/logout UI controls
"""

import logging

import httpx
import streamlit as st
from fastapi import status
from httpx import HTTPStatusError, RequestError

from agentic_scraper import __api_version__ as api_version
from agentic_scraper.backend.config.constants import EXPECTED_JWT_PARTS
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_JWT_FROM_URL,
    MSG_EXCEPTION_OPENAI_CREDENTIALS,
    MSG_EXCEPTION_OPENAI_CREDENTIALS_NETWORK,
    MSG_EXCEPTION_USER_PROFILE,
    MSG_EXCEPTION_USER_PROFILE_NETWORK,
    MSG_INFO_AUTH0_LOGIN_URI,
    MSG_INFO_CREDENTIALS_SUCCESS,
    MSG_INFO_NO_TOKEN_YET,
    MSG_INFO_TOKEN_SESSION_LENGTH,
    MSG_INFO_USER_PROFILE_SUCCESS,
    MSG_WARNING_MALFORMED_JWT,
    MSG_WARNING_NO_JWT_FOUND,
)
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.backend.scraper.models import OpenAIConfig

logger = logging.getLogger(__name__)
settings = get_settings()


def get_jwt_token_from_url() -> str | None:
    """
    Extract the JWT token from the URL query parameters or session state.

    Returns:
        str | None: Valid JWT token, if found.
    """
    token = st.query_params.get("token")

    if token:
        jwt_token = token[0] if isinstance(token, list) else token
        if isinstance(jwt_token, str) and len(jwt_token.split(".")) == EXPECTED_JWT_PARTS:
            st.session_state["jwt_token"] = jwt_token
            logger.debug(MSG_DEBUG_JWT_FROM_URL.format(token=jwt_token))
            st.query_params.clear()
            return jwt_token
        logger.warning(MSG_WARNING_MALFORMED_JWT.format(token=jwt_token))
        st.warning("⚠️ Token format appears invalid. Login may fail.")
        return None

    token_from_session = st.session_state.get("jwt_token")
    if token_from_session:
        logger.debug("Token from session state (not URL)")
    else:
        logger.warning(MSG_WARNING_NO_JWT_FOUND)
    return token_from_session


def ensure_https(domain: str) -> str:
    """
    Ensure the given domain starts with https:// for secure links.

    Args:
        domain (str): Auth0 or frontend domain.

    Returns:
        str: Secure domain URL.
    """
    if not domain.startswith("http"):
        return "https://" + domain
    return domain


def fetch_user_profile() -> None:
    """
    Fetch the user's profile from the backend `/user/me` endpoint.

    Stores user info in session state if successful.

    Raises:
        Displays error in UI if request fails or session is invalid.
    """
    if not st.session_state.get("jwt_token"):
        st.error("User is not authenticated!")
        return

    headers = {"Authorization": f"Bearer {st.session_state['jwt_token']}"}
    backend_api = settings.auth0_api_audience.rstrip("/")
    try:
        response = httpx.get(f"{backend_api}/api/{api_version}/user/me", headers=headers)
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            st.warning("Session expired. Please log in again.")
            logout_user()
            return
        response.raise_for_status()
    except HTTPStatusError as e:
        logger.exception(MSG_EXCEPTION_USER_PROFILE.format(error=e.response.text))
        st.error(f"Failed to fetch user profile: {e.response.text}")
    except RequestError as e:
        logger.exception(MSG_EXCEPTION_USER_PROFILE_NETWORK)
        st.error(f"Network error while fetching user profile: {e}")
    else:
        logger.info(MSG_INFO_USER_PROFILE_SUCCESS)
        logger.info(MSG_INFO_CREDENTIALS_SUCCESS)
        st.session_state["user_info"] = response.json()


def fetch_openai_credentials() -> None:
    """
    Fetch the user's OpenAI credentials from the backend.

    Stores credentials in session state if successful.

    Raises:
        Displays error in UI if request fails or session is invalid.
    """
    if "jwt_token" not in st.session_state:
        st.error("User is not authenticated!")
        return

    headers = {"Authorization": f"Bearer {st.session_state['jwt_token']}"}
    backend_api = settings.auth0_api_audience.rstrip("/")
    try:
        with httpx.Client() as client:
            response = client.get(
                f"{backend_api}/api/{api_version}/user/openai-credentials",
                headers=headers,
            )
            if response.status_code == status.HTTP_401_UNAUTHORIZED:
                st.warning("Session expired. Please log in again.")
                logout_user()
                return
            response.raise_for_status()
    except HTTPStatusError as e:
        logger.exception(MSG_EXCEPTION_OPENAI_CREDENTIALS.format(error=e.response.text))
        st.error(f"Failed to fetch OpenAI credentials: {e.response.text}")
    except RequestError as e:
        logger.exception(MSG_EXCEPTION_OPENAI_CREDENTIALS_NETWORK)
        st.error(f"Network error while fetching OpenAI credentials: {e}")
    else:
        data = response.json()
        openai_config = OpenAIConfig(
            api_key=data.get("api_key"),
            project_id=data.get("project_id"),
        )
        st.session_state["openai_credentials"] = openai_config
        st.success("OpenAI credentials retrieved successfully!")


def authenticate_user() -> None:
    """
    Authenticate the user by extracting the JWT and fetching their profile and credentials.

    Returns:
        None
    """
    if "jwt_token" in st.session_state and "user_info" in st.session_state:
        return

    jwt_token = get_jwt_token_from_url()
    if jwt_token:
        if len(jwt_token.split(".")) != EXPECTED_JWT_PARTS:
            logger.warning(MSG_WARNING_MALFORMED_JWT.format(token=jwt_token))
            st.warning("⚠️ Token format appears invalid. Login may fail.")

        logger.info(MSG_INFO_TOKEN_SESSION_LENGTH.format(length=len(jwt_token)))
        fetch_user_profile()
        fetch_openai_credentials()
        st.success("Logged in successfully!")
        st.rerun()
    else:
        logger.info(MSG_INFO_NO_TOKEN_YET)


def logout_user() -> None:
    """
    Clear authentication-related session data and refresh UI.

    Returns:
        None
    """
    st.session_state.pop("jwt_token", None)
    st.session_state.pop("user_info", None)
    st.session_state.pop("openai_credentials", None)
    st.success("Logged out successfully!")
    st.rerun()


def login_ui(agent_mode: str) -> None:
    """
    Render login or logout UI components based on current session state.

    Args:
        agent_mode (str): The currently selected agent mode.

    Returns:
        None
    """
    requires_auth = agent_mode and agent_mode != "rule_based"
    if not requires_auth:
        return

    if "jwt_token" not in st.session_state:
        with st.sidebar:
            st.markdown("Click below to log in:")

            frontend = settings.frontend_domain.strip().rstrip("/")
            if not frontend.startswith("http://") and not frontend.startswith("https://"):
                frontend = "https://" + frontend

            login_url = (
                f"https://{settings.auth0_domain}/authorize"
                f"?client_id={settings.auth0_client_id}"
                f"&response_type=code"
                f"&redirect_uri={settings.auth0_redirect_uri}"
                f"&audience={settings.auth0_api_audience}"
                f"&scope=openid%20profile%20email%20create:openai_credentials%20read:user_profile"
            )

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
        with st.sidebar:
            user_info = st.session_state.get("user_info", {})
            st.markdown(f"Welcome, **{user_info.get('name', 'User')}**")
            st.markdown(f"📧 Email: `{user_info.get('email', 'N/A')}`")

            if st.button("Logout"):
                logout_user()
