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
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.frontend.ui_auth import fetch_openai_credentials

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

    if "openai_credentials" in st.session_state:
        st.success("✅ Credentials already stored.")
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
                st.session_state.pop("confirm_delete", None)
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
        return True
