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

import logging
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import streamlit as st

from agentic_scraper.backend.config.constants import REQUIRED_CONFIG_FIELDS_FOR_LLM
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_CACHE_DECISION,
    MSG_DEBUG_LLM_FIELDS_ATTACHED,
    MSG_DEBUG_PARSE_RESULT_SUMMARY,
    MSG_DEBUG_PIPELINE_INPUT,
    MSG_DEBUG_RESPONSE_BODY_COMPACT,
    MSG_INFO_INLINE_KEY_MASKED_FALLBACK,
    MSG_INFO_NO_VALID_URLS,
    MSG_INFO_VALID_URLS_FOUND,
    MSG_WARNING_PARSE_ITEM_SKIPPED,
)
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

logger = logging.getLogger(__name__)

DOMAIN_EMOJIS = {
    "youtube.com": "🎮",
    "github.com": "💻",
    "amazon.com": "🎭",
    "medium.com": "✍️",
    "wikipedia.org": "📚",
    "google.com": "🔎",
}

MASK_CHARS: set[str] = {"*", "•", "●", "·"}
MASK_WORDS: set[str] = {"redacted", "masked", "hidden"}


PREVIEW_LIMIT = 10


def _looks_masked(s: str | None) -> bool:
    """
    Heuristically detect redacted/masked secrets.
    Flags common mask characters (*, •, ●, ·) or placeholder words.
    """
    if not isinstance(s, str) or not s:
        return False
    if any(ch in s for ch in MASK_CHARS):
        return True
    ls = s.lower()
    return any(w in ls for w in MASK_WORDS)


def validate_and_deduplicate_urls(raw_input: str) -> tuple[list[str], list[str]]:
    """Clean and deduplicate user input URLs, separating valid and invalid ones."""
    all_lines = [line.strip() for line in raw_input.strip().splitlines() if line.strip()]
    valid_urls = clean_input_urls(raw_input)
    invalid_lines = [line for line in all_lines if line not in valid_urls]
    deduped = deduplicate_urls(valid_urls)

    with suppress(Exception):
        logger.debug(
            MSG_DEBUG_PIPELINE_INPUT.format(valid=len(deduped), invalid=len(invalid_lines))
        )
        if len(deduped) != len(valid_urls):
            key_summary = f"{len(valid_urls)}→{len(deduped)}"
            logger.debug(MSG_DEBUG_CACHE_DECISION.format(decision="DEDUP", key=key_summary))
        if invalid_lines:
            preview = ", ".join(invalid_lines[:PREVIEW_LIMIT])
            if len(invalid_lines) > PREVIEW_LIMIT:
                preview += ", ...(truncated)"
            logger.debug(MSG_DEBUG_RESPONSE_BODY_COMPACT.format(body=preview))

    return deduped, invalid_lines


def extract_domain_icon(url: str) -> str:
    """Return an emoji icon representing a known domain, defaulting to a link icon."""
    for domain, emoji in DOMAIN_EMOJIS.items():
        if domain in url:
            return emoji
    return "🔗"


def summarize_results(items: Sequence[Mapping[str, Any]], skipped: int, start_time: float) -> None:
    """Display scraping performance metrics and a quick view of results."""
    elapsed = round(time.perf_counter() - start_time, 2)

    if not items:
        st.warning("⚠️ No data could be extracted.")
        with suppress(Exception):
            key = f"skipped={skipped} elapsed={elapsed}"
            logger.debug(MSG_DEBUG_CACHE_DECISION.format(decision="NO_ITEMS", key=key))
        return

    st.markdown("## 🎉 Extraction Complete")
    col1, col2, col3 = st.columns(3)
    col1.metric("✅ Extracted", f"{len(items)} URLs")
    col2.metric("⚠️ Skipped", f"{skipped} URLs")
    col3.metric("⏱️ Time", f"{elapsed:.2f}s")

    with st.expander("🔍 Extracted URLs (Quick View)"):
        for item in items:
            # dict-safe access (fallbacks included)
            url = item.get("url") if isinstance(item, dict) else getattr(item, "url", "")
            title = item.get("title") if isinstance(item, dict) else getattr(item, "title", None)
            url_str = str(url) if url is not None else ""
            title_str = (title or url_str).strip()
            icon = extract_domain_icon(url_str)
            st.markdown(f"- {icon} [{title_str}]({url_str})")


def render_invalid_url_section(invalid_lines: list[str]) -> None:
    """Show an expandable UI section listing invalid input URLs."""
    if invalid_lines:
        with suppress(Exception):
            body = f"invalid_count={len(invalid_lines)}"
            logger.debug(MSG_DEBUG_RESPONSE_BODY_COMPACT.format(body=body))
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
        with suppress(Exception):
            body = f"valid_count={len(urls)}"
            logger.debug(MSG_DEBUG_RESPONSE_BODY_COMPACT.format(body=body))


def attach_openai_config(config: PipelineConfig, body: dict[str, Any]) -> bool:
    """
    Attach inline OpenAI credentials only if present and unmasked.
    Always attach LLM params; if creds are masked/missing, omit them so the backend
    can use stored credentials.
    """
    openai_credentials = st.session_state.get("openai_credentials")

    # Normalize creds payload (Pydantic v2 model or plain mapping)
    creds_payload: dict[str, Any] | None = None
    if openai_credentials is not None:
        if hasattr(openai_credentials, "model_dump"):
            creds_payload = openai_credentials.model_dump()
        elif isinstance(openai_credentials, Mapping):
            creds_payload = dict(openai_credentials)

    # Attach inline creds only if present and not masked
    if creds_payload:
        api_key = creds_payload.get("api_key")
        if isinstance(api_key, str) and not _looks_masked(api_key) and api_key:
            body["openai_credentials"] = creds_payload
        else:
            with suppress(Exception):
                logger.info(MSG_INFO_INLINE_KEY_MASKED_FALLBACK)

    # Attach optional LLM params from config
    openai_model = getattr(config, "openai_model", None)
    llm_concurrency = getattr(config, "llm_concurrency", None)
    llm_schema_retries = getattr(config, "llm_schema_retries", None)

    if openai_model is not None:
        body["openai_model"] = openai_model
    if llm_concurrency is not None:
        body["llm_concurrency"] = llm_concurrency
    if llm_schema_retries is not None:
        body["llm_schema_retries"] = llm_schema_retries

    with suppress(Exception):
        fields = [k for k in REQUIRED_CONFIG_FIELDS_FOR_LLM if k in body]
        logger.debug(MSG_DEBUG_LLM_FIELDS_ATTACHED.format(fields=fields))

    return True


# -------------------------
# New helpers for job-based flow
# -------------------------
def parse_job_result(job: dict[str, Any]) -> tuple[list[dict[str, Any]], int, float]:
    """
    Convert a final job payload (status == succeeded) into plain dict items + stats.

    Returns:
        (items, skipped, duration_sec)
        - items: list[dict[str, Any]] with ALL fields preserved (including dynamic extras)
    """
    result = (job or {}).get("result") or {}
    raw_items = result.get("items", [])
    stats = result.get("stats", {}) or {}
    skipped = int(stats.get("num_failed", 0) or 0)
    duration = float(stats.get("duration_sec", 0.0) or 0.0)

    items: list[dict[str, Any]] = []
    malformed = 0

    for idx, item in enumerate(raw_items):
        # Already a dict → keep as-is to preserve dynamic fields
        if isinstance(item, dict):
            items.append(item)
            continue

        # Pydantic-like object → try model_dump()/dict() to get a plain dict
        try:
            md = getattr(item, "model_dump", None)
            if callable(md):
                items.append(md())
                continue

            d = getattr(item, "dict", None)  # Pydantic v1 fallback
            if callable(d):
                items.append(d())
                continue
        except (AttributeError, TypeError) as e:
            malformed += 1
            # Log and surface a warning; no broad suppress/except to satisfy Ruff BLE001
            logger.warning(MSG_WARNING_PARSE_ITEM_SKIPPED.format(idx=idx + 1, error=str(e)))
            st.warning(f"⚠️ Skipped malformed result #{idx + 1}: {e}")
            continue
        # Anything else → skip with warning
        malformed += 1
        with suppress(Exception):
            typ = type(item).__name__
            logger.warning(MSG_WARNING_PARSE_ITEM_SKIPPED.format(idx=idx + 1, error=typ))
        st.warning(f"⚠️ Skipped unexpected type result #{idx + 1}: {type(item)}")

    with suppress(Exception):
        logger.debug(
            MSG_DEBUG_PARSE_RESULT_SUMMARY.format(
                raw=len(raw_items),
                valid=len(items),
                malformed=malformed,
                num_failed=skipped,
                duration=f"{duration:.2f}",
            )
        )

    return items, skipped, duration


def render_job_error(job: dict[str, Any]) -> None:
    """Render a terminal job error or cancellation message in the UI."""
    status_ = (job.get("status") or "").lower()
    if status_ == "canceled":
        st.info("🛑 Job was canceled.")
        return

    err = job.get("error")
    if isinstance(err, dict) and "message" in err:
        msg = err.get("message")
    else:
        msg = str(err) if err else "Job failed."
    with suppress(Exception):
        logger.warning(MSG_DEBUG_RESPONSE_BODY_COMPACT.format(body=f"job_error={msg}"))
    st.error(msg)
