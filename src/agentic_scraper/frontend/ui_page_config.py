"""
Page configuration and input method selection for the Streamlit frontend.

Responsibilities:
- Configure Streamlit page metadata (title/layout) and render project branding.
- Fetch/cache the project logo (with graceful network failure handling).
- Provide two input methods for URLs: pasted text or uploaded `.txt` file.
- Decode uploaded file content and return a raw, newline-separated URL string.

Public API:
- `configure_page`: Apply page config, render the logo and intro copy.
- `render_input_section`: Render input controls and return raw URL text.

Operational:
- Network: Uses a short-lived `httpx.Client` to fetch the logo; cached for 24h.
- Platform: On Windows, adopts `WindowsProactorEventLoopPolicy` for asyncio compatibility.
- UI: Streamlit-based; decoding/upload errors are surfaced via `st.error`.

Usage:
    configure_page()
    raw_input = render_input_section()

Notes:
- `st.set_page_config(...)` must be called early in the app before other Streamlit rendering.
- The logo request is best-effort; the UI proceeds even if the image can't be fetched.
"""

import asyncio
import sys

import httpx
import streamlit as st

# Windows asyncio compatibility (keep before any event-loop usage).
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

LOGO_URL = "https://raw.githubusercontent.com/berserkhmdvhb/agentic-scraper/main/logo.png"

__all__ = ["configure_page", "render_input_section"]


@st.cache_data(ttl=86400, show_spinner=False)
def _load_logo_bytes(url: str) -> bytes | None:
    """
    Fetch the project logo bytes and cache them to avoid repeated network calls.

    Args:
        url (str): Absolute URL of the logo image.

    Returns:
        bytes | None: Image bytes on success; None if the fetch fails.

    Notes:
        - Network and HTTP errors are intentionally swallowed; the UI degrades gracefully.
        - The TTL is one day (86400 seconds) to keep cold-starts fast without overfetching.
    """
    try:
        with httpx.Client() as client:
            return client.get(url, timeout=10).content
    except (httpx.RequestError, httpx.HTTPStatusError):
        return None


def configure_page() -> None:
    """
    Configure Streamlit page metadata and render branding + intro copy.

    Behavior:
        - Sets the page title and layout to "wide".
        - Tries to render the cached logo (if available).
        - Shows a short description of the app.

    Returns:
        None

    Examples:
        # Call once near the top of your Streamlit script:
        configure_page()

    Notes:
        - Keep this invocation early in your script, as Streamlit expects
          `st.set_page_config` to run before other rendering calls.
    """
    st.set_page_config(page_title="Agentic Scraper", layout="wide")

    # Best-effort: missing/failed logo fetch should not block the page.
    logo = _load_logo_bytes(LOGO_URL)
    if logo:
        st.image(logo, width=300)

    st.markdown("Extract structured data from any list of URLs using LLM-powered parsing.")


def render_input_section() -> str:
    """
    Render a section allowing the user to input URLs via text box or file upload.

    UI:
        - "Paste URLs": Multi-line text area (one URL per line).
        - "Upload .txt file": Reads and UTF-8 decodes file contents.

    Returns:
        str: Raw, newline-separated URL string (may be empty).

    Examples:
        raw_input = render_input_section()
        # -> "https://example.com\\nhttps://another.com"

    Notes:
        - Decoding errors from uploaded files are caught and shown to the user;
          the function then returns an empty string to indicate no usable input.
    """
    input_method = st.radio("Input method:", ["Paste URLs", "Upload .txt file"], horizontal=True)

    if input_method == "Paste URLs":
        return st.text_area(
            "Enter one URL per line:",
            height=200,
            placeholder="https://example.com\nhttps://another.com",
        )

    if input_method == "Upload .txt file":
        uploaded_file = st.file_uploader("Upload a .txt file with URLs", type=["txt"])
        if uploaded_file:
            try:
                # We expect UTF-8 text input; errors are reported inline without raising.
                return uploaded_file.read().decode("utf-8")
            except UnicodeDecodeError:
                st.error("❌ Unable to decode file. Please upload a UTF-8 encoded .txt file.")

    return ""
