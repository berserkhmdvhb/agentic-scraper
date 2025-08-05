"""
Render UI form for submitting OpenAI credentials in the Streamlit frontend.

This module:
- Allows logged-in users to submit their OpenAI API key and project ID
- Posts the credentials to the backend for secure storage
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

    Raises:
        None directly, but displays errors via Streamlit.
    """
    st.markdown("### 🔑 Enter OpenAI Credentials")

    if "openai_saved" in st.session_state:
        st.success("✅ Credentials already saved.")
        return

    with st.form("openai_credentials_form"):
        api_key = st.text_input("OpenAI API Key", type="password")
        project_id = st.text_input("OpenAI Project ID").strip()
        submitted = st.form_submit_button("Save Credentials")

        if submitted:
            if not api_key or not project_id:
                st.error("Both API key and Project ID are required.")
                return

            if "jwt_token" not in st.session_state:
                st.error("You must be logged in to submit credentials.")
                return

            headers = {"Authorization": f"Bearer {st.session_state['jwt_token']}"}
            data = {"api_key": api_key, "project_id": project_id}

            try:
                with st.spinner("Saving credentials..."):
                    response = httpx.post(
                        f"{settings.backend_domain}/api/{api_version}/user/openai-credentials",
                        json=data,
                        headers=headers,
                        timeout=10,
                    )
                    response.raise_for_status()

                st.success("✅ OpenAI credentials saved successfully!")
                st.session_state["openai_saved"] = True
                fetch_openai_credentials()

            except httpx.HTTPStatusError as e:
                st.error(f"❌ Failed to save credentials: {e.response.text}")
            except httpx.RequestError as e:
                st.error("⚠️ A network error occurred while saving credentials.")
                if settings.is_verbose_mode:
                    st.exception(e)
