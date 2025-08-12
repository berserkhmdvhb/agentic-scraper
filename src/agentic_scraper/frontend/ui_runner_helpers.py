"""
Helper functions for the Streamlit scraper runner (REST job flow).

This module now focuses on:
- Input URL validation and deduplication
- Optional OpenAI config attachment (when overriding stored creds)
- Parsing final job results into ScrapedItem objects
- UI feedback for valid/invalid inputs and terminal job errors
- Quick result summaries
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import streamlit as st
from pydantic import ValidationError

from agentic_scraper.backend.config.messages import (
    MSG_INFO_NO_VALID_URLS,
    MSG_INFO_VALID_URLS_FOUND,
)
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.backend.utils.validators import clean_input_urls, deduplicate_urls

if TYPE_CHECKING:
    from agentic_scraper.frontend.models import PipelineConfig

__all__ = [
    "attach_openai_config",
    "extract_domain_icon",
    "parse_job_result",
    "render_invalid_url_section",
    "render_job_error",
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
    """Clean and deduplicate user input URLs, separating valid and invalid ones."""
    all_lines = [line.strip() for line in raw_input.strip().splitlines() if line.strip()]
    valid_urls = clean_input_urls(raw_input)
    invalid_lines = [line for line in all_lines if line not in valid_urls]
    return deduplicate_urls(valid_urls), invalid_lines


def extract_domain_icon(url: str) -> str:
    """Return an emoji icon representing a known domain, defaulting to a link icon."""
    for domain, emoji in DOMAIN_EMOJIS.items():
        if domain in url:
            return emoji
    return "🔗"


def summarize_results(items: list[ScrapedItem], skipped: int, start_time: float) -> None:
    """Display scraping performance metrics and a quick view of results."""
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
    """Show an expandable UI section listing invalid input URLs."""
    if invalid_lines:
        with st.expander("⚠️ Skipped Invalid URLs"):
            for url in invalid_lines:
                st.markdown(f"- ❌ `{url}` — *invalid URL format*")


def render_valid_url_feedback(urls: list[str]) -> None:
    """Show feedback in the UI when valid URLs are detected."""
    if not urls:
        st.warning(MSG_INFO_NO_VALID_URLS)
    else:
        st.session_state.valid_urls = urls
        st.info(MSG_INFO_VALID_URLS_FOUND.format(n=len(urls)))
        st.markdown("---")


def attach_openai_config(config: PipelineConfig, body: dict[str, Any]) -> bool:
    """
    Optionally inject OpenAI credentials and LLM parameters into the request body.

    Returns True if credentials were attached, False if missing (and shows a UI error).
    """
    openai_credentials = st.session_state.get("openai_credentials")
    if not openai_credentials:
        st.error("OpenAI credentials are missing!")
        return False

    body.update(
        {
            "openai_credentials": openai_credentials.model_dump(),
            "openai_model": getattr(config, "openai_model", None),
            "llm_concurrency": getattr(config, "llm_concurrency", None),
            "llm_schema_retries": getattr(config, "llm_schema_retries", None),
        }
    )
    # Strip None fields so payload is clean
    for k in ["openai_model", "llm_concurrency", "llm_schema_retries"]:
        if body.get(k) is None:
            body.pop(k, None)
    return True


# -------------------------
# New helpers for job-based flow
# -------------------------


def parse_job_result(job: dict[str, Any]) -> tuple[list[ScrapedItem], int, float]:
    """
    Convert a final job payload (status == succeeded) into typed items + stats.

    Returns (items, skipped, duration_sec).
    """
    result = (job or {}).get("result") or {}
    raw_items = result.get("items", [])
    stats = result.get("stats", {})
    skipped = int(stats.get("num_failed", 0) or 0)
    duration = float(stats.get("duration_sec", 0.0) or 0.0)

    items: list[ScrapedItem] = []
    for idx, item in enumerate(raw_items):
        if isinstance(item, ScrapedItem):
            items.append(item)
            continue
        if isinstance(item, dict):
            try:
                items.append(ScrapedItem(**item))
            except (ValidationError, TypeError) as e:
                st.warning(f"⚠️ Skipped malformed result #{idx + 1}: {e}")
        else:
            st.warning(f"⚠️ Skipped unexpected type result #{idx + 1}: {type(item)}")

    return items, skipped, duration


def render_job_error(job: dict[str, Any]) -> None:
    """Render a terminal job error or cancellation message in the UI."""
    status_ = (job.get("status") or "").lower()
    if status_ == "canceled":
        st.info("🛑 Job was canceled.")
        return

    # failed or unknown
    err = job.get("error")
    if isinstance(err, dict) and "message" in err:
        msg = err.get("message")
    else:
        msg = str(err) if err else "Job failed."
    st.error(msg)
