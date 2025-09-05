"""
Render a Streamlit UI form for managing OpenAI credentials.

Responsibilities:
- Render a form for logged-in users to submit OpenAI API key + project ID.
- Persist credentials via backend endpoints (PUT/DELETE).
- Provide update/delete actions with safe confirmation.
- Reflect backend state via lightweight status probes and previews.

Public API:
- `render_credentials_form`: Main entry point to render the credentials UI.
- `render_credentials_actions`: Render update/delete actions (when creds exist).
- `put_openai_credentials`: Store credentials through the backend API.
- `delete_openai_credentials`: Delete credentials through the backend API.

Config:
- Reads environment-backed values via `get_settings()` (e.g., backend_domain, verbosity).
- Uses package `__api_version__` to route calls to the correct API version.

Operational:
- Network: Synchronous `httpx` calls with short timeouts and Streamlit spinners.
- Logging/UI: Surfaces HTTP/network failures to the user; verbose mode shows tracebacks.

Usage:
    # In a Streamlit page/tab:
    render_credentials_form()

Notes:
- This module only renders the credentials management UI. The *preview* fetch and
  auth helpers live in `frontend/ui_auth_helpers.py`.
- When credentials are saved, we keep an unmasked copy in `st.session_state["openai_credentials"]`
  for inline use, and optionally fetch a masked preview for display.
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
    Render the credentials entry experience for OpenAI API key + project ID.

    Behavior:
        - If the user already has credentials, show a success state, an optional
          masked preview (if available), and management actions instead of the form.
        - If the state is unknown (e.g., deep-link to this view), probe the backend
          for a status first.

    Returns:
        None

    Examples:
        # In your Streamlit app layout:
        render_credentials_form()

    Notes:
        - The actual storage request is performed by `put_openai_credentials()`.
        - On success, `st.rerun()` is used to refresh the UI and reflect new state.
    """
    st.markdown("### 🔑 Enter OpenAI Credentials")

    # Lazy-init the status flag if it's missing (e.g., user deep-linked into this tab).
    if "has_openai_credentials" not in st.session_state:
        status = fetch_openai_credentials_status()
        if status is not None:
            st.session_state["has_openai_credentials"] = bool(status.get("has_credentials"))

    # If credentials exist, show a success state and actions (not the initial form).
    if st.session_state.get("has_openai_credentials"):
        st.success("✅ Credentials already stored.")
        preview = st.session_state.get("openai_credentials_preview")
        if isinstance(preview, dict):
            # Safe to display: api_key is expected to be masked by the backend/helper.
            st.write(f"**Project ID:** `{preview.get('project_id', '')}`")
            st.write(f"**API Key:** `{preview.get('api_key', '****')}`")
        render_credentials_actions()
        return

    # Initial capture form (only shown if we do not have credentials yet).
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

            # Persist via backend. On success, refresh to reflect new state.
            if put_openai_credentials(api_key, project_id):
                st.session_state["has_openai_credentials"] = True
                st.rerun()


def render_credentials_actions() -> None:
    """
    Render action controls to update or delete existing credentials.

    UI Flow:
        - "Update Credentials" clears the local stored values and reruns,
          showing the initial form again.
        - "Delete Credentials" exposes a confirmation expander; deletion then
          clears flags and previews, and reruns the app.

    Returns:
        None

    Notes:
        - We use an expander-based confirmation to avoid accidental deletions.
        - Reruns ensure the UI reflects the latest state after mutation.
    """
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Update Credentials"):
            # Clear local (unmasked) creds + masked preview; show the form on next run.
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
                # Clear local copies and flags on successful deletion.
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
    Store the user's OpenAI credentials by calling the backend (`PUT /user/openai-credentials`).

    Args:
        api_key (str): The user's OpenAI API key (unmasked).
        project_id (str): The user's OpenAI project ID.

    Returns:
        bool: True on success, False on any HTTP/network error or unauthenticated session.

    Examples:
        ok = put_openai_credentials("sk-...", "proj_123")
        if ok:
            st.success("Saved!")

    Notes:
        - Requires a valid JWT in `st.session_state["jwt_token"]`.
        - On success, stores an unmasked `OpenAIConfig` locally for inline use,
          and then calls `fetch_openai_credentials()` to retrieve a masked preview for display.
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
            st.exception(e)  # Streamlit-friendly traceback in verbose mode
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
    Delete the user's OpenAI credentials by calling the backend (`DELETE /user/openai-credentials`).

    Returns:
        bool: True on success, False on any HTTP/network error or unauthenticated session.

    Examples:
        if delete_openai_credentials():
            st.success("Deleted.")

    Notes:
        - Requires a valid JWT in `st.session_state["jwt_token"]`.
        - On success, caller is responsible for clearing local state and rerunning.
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
