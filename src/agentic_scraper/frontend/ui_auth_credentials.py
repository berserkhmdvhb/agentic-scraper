"""
Render UI form for submitting OpenAI credentials in the Streamlit frontend.

This module:
- Allows logged-in users to submit their OpenAI API key and project ID
- Posts the credentials to the backend for secure storage
- Allows users to update or delete their credentials
- Provides validation and feedback for form submission
"""

import httpx
import streamlit as st

from agentic_scraper import __api_version__ as api_version
from agentic_scraper.backend.config.types import OpenAIConfig
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.frontend.ui_auth_helpers import (
    fetch_openai_credentials,
    fetch_openai_credentials_status,
)

settings = get_settings()


def render_credentials_form() -> None:
    """
    Display a form for the user to enter OpenAI API credentials.

    Submits credentials to the backend for encrypted storage. Provides
    feedback based on success or failure of the HTTP request.

    Returns:
        None
    """
    st.markdown("### 🔑 Enter OpenAI Credentials")
    # Lazy-init the status flag if it's missing (e.g., deep-link into this tab)
    if "has_openai_credentials" not in st.session_state:
        status = fetch_openai_credentials_status()
        if status is not None:
            st.session_state["has_openai_credentials"] = bool(status.get("has_credentials"))

    # If user already has credentials, show actions
    # (and optional masked preview), not the initial form
    if st.session_state.get("has_openai_credentials"):
        st.success("✅ Credentials already stored.")
        preview = st.session_state.get("openai_credentials_preview")
        if isinstance(preview, dict):
            # Safe to display: api_key should be masked by the backend helper
            st.write(f"**Project ID:** `{preview.get('project_id', '')}`")
            st.write(f"**API Key:** `{preview.get('api_key', '****')}`")
        render_credentials_actions()
        return

    with st.form("openai_credentials_form"):
        api_key = st.text_input("OpenAI API Key", type="password")
        project_id = st.text_input("OpenAI Project ID")
        submitted = st.form_submit_button("Save Credentials")

        if submitted:
            api_key = api_key.strip()
            project_id = project_id.strip()

            if not api_key or not project_id:
                st.error("Both API key and Project ID are required.")
                return

            if put_openai_credentials(api_key, project_id):
                st.session_state["has_openai_credentials"] = True
                st.rerun()


def render_credentials_actions() -> None:
    """
    Display update and delete buttons for managing stored credentials.

    Returns:
        None
    """
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Update Credentials"):
            st.session_state.pop("openai_credentials")
            st.session_state.pop("openai_credentials_preview", None)
            st.rerun()

    with col2:
        if st.button("🗑️ Delete Credentials"):
            st.session_state["confirm_delete"] = True

    if st.session_state.get("confirm_delete"):
        with st.expander("⚠️ Confirm Delete"):
            confirm = st.button("✅ Yes, delete credentials")
            cancel = st.button("❌ Cancel")

            if confirm and delete_openai_credentials():
                st.session_state.pop("openai_credentials", None)
                st.session_state.pop("openai_credentials_preview", None)
                st.session_state.pop("confirm_delete", None)
                st.session_state["has_openai_credentials"] = False
                st.success("✅ Credentials deleted successfully.")
                st.rerun()

            if cancel:
                st.session_state.pop("confirm_delete", None)


def put_openai_credentials(api_key: str, project_id: str) -> bool:
    """
    Send a PUT request to save the user's OpenAI credentials.

    Args:
        api_key (str): The user's OpenAI API key.
        project_id (str): The user's OpenAI project ID.

    Returns:
        bool: True if credentials were saved successfully, False otherwise.
    """
    if "jwt_token" not in st.session_state:
        st.error("You must be logged in to submit credentials.")
        return False

    headers = {"Authorization": f"Bearer {st.session_state['jwt_token']}"}
    data = {"api_key": api_key, "project_id": project_id}

    try:
        with st.spinner("Saving credentials..."):
            response = httpx.put(
                f"{settings.backend_domain}/api/{api_version}/user/openai-credentials",
                json=data,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        st.error(f"❌ Failed to save credentials: {e.response.text}")
        return False
    except httpx.RequestError as e:
        st.error("⚠️ A network error occurred while saving credentials.")
        if settings.is_verbose_mode:
            st.exception(e)
        return False
    else:
        st.success("✅ OpenAI credentials saved successfully!")
        # Preserve the real (unmasked) creds in session for inline use.
        openai_config = OpenAIConfig(
            api_key=data.get("api_key"),
            project_id=data.get("project_id"),
        )
        st.session_state["openai_credentials"] = openai_config
        # Optionally fetch masked preview for UI without clobbering the real creds.
        fetch_openai_credentials()
        return True


def delete_openai_credentials() -> bool:
    """
    Send a DELETE request to remove the user's stored OpenAI credentials.

    Returns:
        bool: True if deletion was successful, False otherwise.
    """
    if "jwt_token" not in st.session_state:
        st.error("You must be logged in to delete credentials.")
        return False

    headers = {"Authorization": f"Bearer {st.session_state['jwt_token']}"}

    try:
        with st.spinner("Deleting credentials..."):
            response = httpx.delete(
                f"{settings.backend_domain}/api/{api_version}/user/openai-credentials",
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        st.error(f"❌ Failed to delete credentials: {e.response.text}")
        return False
    except httpx.RequestError as e:
        st.error("⚠️ A network error occurred while deleting credentials.")
        if settings.is_verbose_mode:
            st.exception(e)
        return False
    else:
        st.session_state["has_openai_credentials"] = False
        return True
