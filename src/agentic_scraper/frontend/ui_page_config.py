import asyncio
import sys
from typing import Any

import streamlit as st

from agentic_scraper.backend.config.constants import SESSION_KEYS, VALID_MODEL_OPTIONS
from agentic_scraper.backend.core.logger_setup import setup_logging
from agentic_scraper.backend.core.settings import get_environment, get_log_dir

from agentic_scraper.frontend.ui_auth import login_ui


# Windows asyncio compatibility
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Setup logging once on app start
setup_logging(reset=True)


def configure_page() -> None:
    st.set_page_config(page_title="Agentic Scraper", layout="wide")
    st.image("https://raw.githubusercontent.com/berserkhmdvhb/agentic-scraper/main/logo.png", width=300)
    st.markdown("Extract structured data from any list of URLs using LLM-powered parsing.")
    st.sidebar.markdown(f"**Environment:** `{get_environment()}`")
    st.sidebar.markdown(f"**Log Path:** `{get_log_dir() / 'agentic_scraper.log'}`")

def render_input_section() -> str | None:
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
