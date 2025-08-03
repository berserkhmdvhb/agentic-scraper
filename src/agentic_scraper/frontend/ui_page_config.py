"""
Page configuration and input method selection for the Streamlit frontend.

This module:
- Sets up the Streamlit page layout, title, and branding
- Displays the logo and introductory markdown
- Offers two input methods: pasted URLs or uploaded .txt file
- Decodes uploaded file content and returns raw input string
"""

import asyncio
import sys

import streamlit as st

from agentic_scraper.core.logger_setup import setup_logging

# Windows asyncio compatibility
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Setup logging once when the app starts
setup_logging(reset=True)


def configure_page() -> None:
    """
    Set up Streamlit page layout, branding, and intro message.

    Returns:
        None
    """
    st.set_page_config(page_title="Agentic Scraper", layout="wide")
    st.image(
        "https://raw.githubusercontent.com/berserkhmdvhb/agentic-scraper/main/logo.png", width=300
    )
    st.markdown("Extract structured data from any list of URLs using LLM-powered parsing.")


def render_input_section() -> str:
    """
    Render a section allowing the user to input URLs either via text box or file upload.

    Returns:
        str: Raw input string containing newline-separated URLs.

    Raises:
        None. All decoding errors are shown via Streamlit error messages.
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
                return uploaded_file.read().decode("utf-8")
            except UnicodeDecodeError:
                st.error("❌ Unable to decode file. Please upload a UTF-8 encoded .txt file.")

    return ""
