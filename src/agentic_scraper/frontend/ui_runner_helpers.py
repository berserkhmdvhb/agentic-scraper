import time
from typing import Any

import streamlit as st
from pydantic import ValidationError

from agentic_scraper.backend.config.messages import (
    MSG_INFO_NO_VALID_URLS,
    MSG_INFO_VALID_URLS_FOUND,
)
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.backend.utils.validators import clean_input_urls, deduplicate_urls
from agentic_scraper.frontend.models import PipelineConfig

__all__ = [
    "attach_openai_config",
    "display_error_summaries",
    "extract_domain_icon",
    "parse_scraper_response",
    "render_invalid_url_section",
    "render_valid_url_feedback",
    "summarize_results",
    "validate_and_deduplicate_urls",
]

DOMAIN_EMOJIS = {
    "youtube.com": "🎮",
    "github.com": "💻",
    "amazon.com": "🎭",
    "medium.com": "✍️",
    "wikipedia.org": "📚",
    "google.com": "🔎",
}


def validate_and_deduplicate_urls(raw_input: str) -> tuple[list[str], list[str]]:
    """
    Split and validate input URLs, returning valid and invalid ones.

    Args:
        raw_input (str): Multiline string of URLs from user input.

    Returns:
        tuple[list[str], list[str]]: Valid deduplicated URLs and invalid lines.
    """

    all_lines = [line.strip() for line in raw_input.strip().splitlines() if line.strip()]
    valid_urls = clean_input_urls(raw_input)
    invalid_lines = [line for line in all_lines if line not in valid_urls]
    return deduplicate_urls(valid_urls), invalid_lines


def extract_domain_icon(url: str) -> str:
    """
    Return an emoji for a known domain or a default link icon.

    Args:
        url (str): The URL to check.

    Returns:
        str: Emoji associated with the domain.
    """
    url = str(url)
    for domain, emoji in DOMAIN_EMOJIS.items():
        if domain in url:
            return emoji
    return "🔗"


def display_error_summaries(fetch_errors: list[str], extraction_errors: list[str]) -> None:
    """
    Render summaries of fetch and extraction errors.

    Args:
        fetch_errors (list[str]): Errors during page loading.
        extraction_errors (list[str]): Errors from LLM or validation.

    Returns:
        None
    """
    if fetch_errors:
        with st.expander("🌐 Fetch Errors (could not load page)"):
            for msg in fetch_errors:
                st.markdown(f"- ❌ `{msg}`")
    if extraction_errors:
        with st.expander("🧐 Extraction Errors (LLM or validation failed)"):
            for msg in extraction_errors:
                st.markdown(f"- ❌ `{msg}`")


def summarize_results(items: list[ScrapedItem], skipped: int, start_time: float) -> None:
    """
    Display metrics and quick view of successful scraping.

    Args:
        items (list[ScrapedItem]): Extracted items.
        skipped (int): Number of skipped URLs.
        start_time (float): Start timestamp.

    Returns:
        None
    """
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
    """
    Show expandable warning for invalid URLs.

    Args:
        invalid_lines (list[str]): Lines from input that failed validation.

    Returns:
        None
    """
    if invalid_lines:
        with st.expander("⚠️ Skipped Invalid URLs"):
            for url in invalid_lines:
                st.markdown(f"- ❌ `{url}` — *invalid URL format*")


def render_valid_url_feedback(urls: list[str]) -> None:
    """
    Show success message if valid URLs found.

    Args:
        urls (list[str]): Validated URLs.

    Returns:
        None
    """
    if not urls:
        st.warning(MSG_INFO_NO_VALID_URLS)
    else:
        st.session_state.valid_urls = urls
        st.info(MSG_INFO_VALID_URLS_FOUND.format(n=len(urls)))
        st.markdown("---")


def attach_openai_config(config: PipelineConfig, body: dict[str, Any]) -> bool:
    """
    Attach OpenAI credentials and model settings to the request body.

    Args:
        config (PipelineConfig): User-selected scraper config.
        body (dict[str, Any]): Request body to be enriched.

    Returns:
        bool: True if credentials were attached successfully, False if missing.
    """
    openai_credentials = st.session_state.get("openai_credentials")
    if not openai_credentials:
        st.error("OpenAI credentials are missing!")
        return False

    body.update(
        {
            "openai_credentials": openai_credentials.model_dump(),
            "openai_model": config.openai_model,
            "llm_concurrency": config.llm_concurrency,
            "llm_schema_retries": config.llm_schema_retries,
        }
    )
    return True


def parse_scraper_response(data: dict) -> tuple[list[ScrapedItem], int]:
    """
    Parse the backend response into structured items and count skipped entries.

    Args:
        data (dict): JSON response from backend.

    Returns:
        tuple[list[ScrapedItem], int]: Parsed items and count of skipped URLs.
    """
    raw_items = data.get("results", [])
    skipped = data.get("stats", {}).get("skipped", 0)
    items = []

    for idx, item in enumerate(raw_items):
        if isinstance(item, dict):
            try:
                items.append(ScrapedItem(**item))
            except (ValidationError, TypeError) as e:
                st.warning(f"⚠️ Skipped malformed result #{idx + 1}: {e}")
        elif isinstance(item, ScrapedItem):
            items.append(item)
        else:
            st.warning(f"⚠️ Skipped unexpected type result #{idx + 1}: {type(item)}")

    return items, skipped
