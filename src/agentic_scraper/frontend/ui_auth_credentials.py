import streamlit as st
import httpx

from agentic_scraper.backend.core.settings import get_settings

settings = get_settings()

def render_credentials_form():
    """Render form for user to input OpenAI credentials."""
    st.markdown("### 🔐 Enter OpenAI Credentials")

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

            headers = {
                "Authorization": f"Bearer {st.session_state['jwt_token']}"
            }
            data = {
                "api_key": api_key,
                "project_id": project_id
            }

            try:
                with st.spinner("Saving credentials..."):
                    response = httpx.post(
                        f"{settings.backend_domain}/api/v1/user/openai-credentials",
                        json=data,
                        headers=headers,
                        timeout=10
                    )
                if response.status_code == 200:
                    st.success("✅ OpenAI credentials saved successfully!")
                    st.session_state["openai_saved"] = True
                else:
                    st.error(f"Failed to save credentials: {response.text}")
            except Exception as e:
                st.error("⚠️ An unexpected error occurred while saving credentials.")
                if settings.is_verbose_mode:
                    st.exception(e)