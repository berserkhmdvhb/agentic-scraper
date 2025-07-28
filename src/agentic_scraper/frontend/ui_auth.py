import logging

import httpx
import streamlit as st
from httpx import HTTPStatusError, RequestError

from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.backend.scraper.models import OpenAIConfig

logger = logging.getLogger(__name__)
settings = get_settings()


def get_jwt_token_from_url() -> str | None:
    """Extract JWT token from query params or session state."""
    token = st.query_params.get("access_token")
    if token:
        st.session_state["jwt_token"] = token
        return token
    return st.session_state.get("jwt_token")


def fetch_user_profile() -> None:
    """Fetch user profile from backend `/me` endpoint and store in session."""
    if not st.session_state.get("jwt_token"):
        st.error("User is not authenticated!")
        return

    headers = {"Authorization": f"Bearer {st.session_state['jwt_token']}"}
    try:
        response = httpx.get(
            f"{settings.auth0_api_audience}/api/v1/user/me",
            headers=headers,
        )
        response.raise_for_status()
    except HTTPStatusError as e:
        message = f"Failed to fetch user profile: {e.response.text}"
        logger.exception(message)
        st.error(message)
    except RequestError as e:
        message = f"Network error while fetching user profile: {e}"
        logger.exception(message)
        st.error(message)
    else:
        st.session_state["user_info"] = response.json()


def fetch_openai_credentials() -> None:
    """Fetch OpenAI credentials from backend and store in session."""
    if "jwt_token" not in st.session_state:
        st.error("User is not authenticated!")
        return

    headers = {"Authorization": f"Bearer {st.session_state['jwt_token']}"}
    try:
        with httpx.Client() as client:
            response = client.get(
                f"{settings.auth0_api_audience}/api/v1/user/openai-credentials",
                headers=headers,
            )
            response.raise_for_status()
    except HTTPStatusError as e:
        message = f"Failed to fetch OpenAI credentials: {e.response.text}"
        logger.exception(message)
        st.error(message)
    except RequestError as e:
        message = f"Network error while fetching OpenAI credentials: {e}"
        logger.exception(message)
        st.error(message)
    else:
        data = response.json()
        openai_config = OpenAIConfig(
            api_key=data.get("api_key"),
            project_id=data.get("project_id"),
        )
        st.session_state["openai_credentials"] = openai_config
        st.success("OpenAI credentials retrieved successfully!")


def authenticate_user() -> None:
    """Authenticate user by extracting JWT and populating session state."""
    if "jwt_token" in st.session_state and "user_info" in st.session_state:
        return  # Already authenticated

    jwt_token = get_jwt_token_from_url()
    if jwt_token:
        st.session_state["jwt_token"] = jwt_token
        fetch_user_profile()
        fetch_openai_credentials()
        st.success("Logged in successfully!")
    else:
        message = "JWT token missing from URL or session."
        logger.warning(message)
        st.error("Login failed!")


def logout_user() -> None:
    """Clear session state and refresh UI."""
    st.session_state.pop("jwt_token", None)
    st.session_state.pop("user_info", None)
    st.session_state.pop("openai_credentials", None)

    st.success("Logged out successfully!")
    st.experimental_rerun()


def login_ui() -> None:
    """Render login/logout buttons based on session state."""
    if "jwt_token" not in st.session_state:
        st.markdown("Click below to log in.")

        # Ensure the trailing slash is present (Auth0 requires it)
        audience = settings.auth0_api_audience
        if not audience.endswith("/"):
            audience += "/"

        login_url = (
            f"https://{settings.auth0_domain}/authorize"
            f"?client_id={settings.auth0_client_id}"
            f"&response_type=token"
            f"&redirect_uri=https://6d35bd763370.ngrok-free.app"
            f"&audience={audience}"
            f"&scope=openid%20profile%20email%20create:openai_credentials"
        )
        print(login_url)
        st.link_button("🔐 Login with Auth0", login_url)

    else:
        user_info = st.session_state.get("user_info", {})
        st.write(f"Welcome, {user_info.get('name', 'User')}")
        st.write(f"Email: {user_info.get('email', 'N/A')}")
        if st.button("Logout"):
            logout_user()
