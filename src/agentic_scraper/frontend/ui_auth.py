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
        if response.status_code == 401:
            st.warning("Session expired. Please log in again.")
            logout_user()
            return
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
            if response.status_code == 401:
                st.warning("Session expired. Please log in again.")
                logout_user()
                return
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


def submit_openai_credentials_ui() -> None:
    """Render OpenAI credential submission form (only shown if logged in)."""
    st.markdown("### 🔑 Submit OpenAI Credentials")

    api_key = st.text_input("OpenAI API Key", type="password")
    project_id = st.text_input("OpenAI Project ID")

    if st.button("Save Credentials"):
        headers = {"Authorization": f"Bearer {st.session_state['jwt_token']}"}
        payload = {"api_key": api_key, "project_id": project_id}

        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{settings.auth0_api_audience}/api/v1/user/openai-credentials",
                    json=payload,
                    headers=headers,
                )
            if response.status_code == 401:
                st.warning("Session expired. Please log in again.")
                logout_user()
                return
            response.raise_for_status()
            st.success("OpenAI credentials saved successfully!")
            fetch_openai_credentials()  # Refresh stored version
        except HTTPStatusError as e:
            logger.exception("Failed to save OpenAI credentials")
            st.error(f"Error: {e.response.text}")
        except RequestError as e:
            logger.exception("Network error while saving OpenAI credentials")
            st.error(f"Network error: {e}")


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


def login_ui(agent_mode: str) -> None:
    """Render login/logout buttons based on session state."""
    requires_auth = agent_mode != "rule_based"
    if not requires_auth:
        return  # Don't show login UI at all if not needed

    if "jwt_token" not in st.session_state:
        st.markdown("Click below to log in.")

        # Normalize frontend domain with scheme
        frontend = settings.frontend_domain.strip().rstrip("/")
        if not frontend.startswith("http://") and not frontend.startswith("https://"):
            frontend = "https://" + frontend

        login_url = (
            f"https://{settings.auth0_domain}/authorize"
            f"?client_id={settings.auth0_client_id}"
            f"&response_type=token"
            f"&redirect_uri={frontend}?route=auth_redirect"
            f"&audience={settings.auth0_api_audience}"
            f"&scope=openid%20profile%20email%20create:openai_credentials"
        )
        st.link_button("🔐 Login with Auth0", login_url)
    else:
        user_info = st.session_state.get("user_info", {})
        st.markdown(f"Welcome, **{user_info.get('name', 'User')}**")
        st.markdown(f"📧 Email: `{user_info.get('email', 'N/A')}`")

        if st.button("Logout"):
            logout_user()

        # Show OpenAI credential form after login
        submit_openai_credentials_ui()
