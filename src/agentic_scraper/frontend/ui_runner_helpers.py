import time
from typing import Any

import streamlit as st

from agentic_scraper.backend.config.messages import (
    MSG_INFO_VALID_URLS_FOUND,
    MSG_INFO_NO_VALID_URLS,
)
from agentic_scraper.backend.scraper.models import ScrapedItem



DOMAIN_EMOJIS = {
    "youtube.com": "🎮",
    "github.com": "💻",
    "amazon.com": "🎭",
    "medium.com": "✍️",
    "wikipedia.org": "📚",
    "google.com": "🔎",
}

def validate_and_deduplicate_urls(raw_input: str) -> tuple[list[str], list[str]]:
    """Split and validate input URLs, returning valid and invalid ones."""
    from agentic_scraper.backend.utils.validators import clean_input_urls, deduplicate_urls

    all_lines = [line.strip() for line in raw_input.strip().splitlines() if line.strip()]
    valid_urls = clean_input_urls(raw_input)
    invalid_lines = [line for line in all_lines if line not in valid_urls]
    return deduplicate_urls(valid_urls), invalid_lines


def extract_domain_icon(url: str) -> str:
    """Return an emoji for a known domain or a default link icon."""
    url = str(url)
    for domain, emoji in DOMAIN_EMOJIS.items():
        if domain in url:
            return emoji
    return "🔗"


def display_error_summaries(fetch_errors: list[str], extraction_errors: list[str]) -> None:
    """Render summaries of fetch and extraction errors."""
    if fetch_errors:
        with st.expander("🌐 Fetch Errors (could not load page)"):
            for msg in fetch_errors:
                st.markdown(f"- ❌ `{msg}`")
    if extraction_errors:
        with st.expander("🧐 Extraction Errors (LLM or validation failed)"):
            for msg in extraction_errors:
                st.markdown(f"- ❌ `{msg}`")


def summarize_results(items: list[ScrapedItem], skipped: int, start_time: float) -> None:
    """Display metrics and quick view of successful scraping."""
    elapsed = round(time.perf_counter() - start_time, 2)

    if not items:
        st.warning("⚠️ No data could be extracted.")
        return

    st.markdown("## 🎉 Extraction Complete")
    col1, col2, col3 = st.columns(3)
    col1.metric("✅ Extracted", f"{len(items)} URLs")
    col2.metric("⚠️ Skipped", f"{skipped} URLs")
    col3.metric("⏱️ Time", f"{elapsed:.2f}s")

    with st.expander("🔍 Extracted URLs (Quick View)"):
        for item in items:
            icon = extract_domain_icon(str(item.url))
            title = (item.title or str(item.url)).strip()
            st.markdown(f"- {icon} [{title}]({item.url})")


def render_invalid_url_section(invalid_lines: list[str]) -> None:
    """Show expandable warning for invalid URLs."""
    if invalid_lines:
        with st.expander("⚠️ Skipped Invalid URLs"):
            for url in invalid_lines:
                st.markdown(f"- ❌ `{url}` — *invalid URL format*")


def render_valid_url_feedback(urls: list[str]) -> None:
    """Show success message if valid URLs found."""
    if not urls:
        st.warning(MSG_INFO_NO_VALID_URLS)
    else:
        st.session_state.valid_urls = urls
        st.info(MSG_INFO_VALID_URLS_FOUND.format(n=len(urls)))
        st.markdown("---")
