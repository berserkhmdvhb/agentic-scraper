"""
Helper functions for the Streamlit scraper runner (REST job flow).

Responsibilities:
- Validate and deduplicate user-entered URLs.
- Attach optional inline OpenAI credentials and LLM parameters to job requests.
- Parse final job payloads into plain dictionaries suitable for UI display/export.
- Render UI feedback for invalid inputs and terminal job errors.
- Provide quick, human-friendly result summaries.

Public API:
- `validate_and_deduplicate_urls`: Clean, validate, and dedupe raw URL input.
- `extract_domain_icon`: Return an emoji for common domains (purely cosmetic).
- `summarize_results`: Render quick metrics + extracted URL list.
- `render_invalid_url_section`: Display expandable UI for invalid URLs.
- `render_valid_url_feedback`: Show UI feedback for detected valid URLs.
- `attach_openai_config`: Insert inline OpenAI/LLM settings into request body.
- `parse_job_result`: Convert a final job payload into (items, skipped, duration).
- `render_job_error`: Render a terminal job error/cancellation message.

Config:
- Uses message constants from `backend.config.messages` for consistent logging/UI text.
- Reads required LLM fields list via `REQUIRED_CONFIG_FIELDS_FOR_LLM` for debug tracing.

Operational:
- Logging: Debug logs are guarded with minimal overhead; sensitive secrets are not written.
- UI: Streamlit-based rendering; errors and warnings are surfaced via `st.error/warning/info`.

Usage:
    urls, bad = validate_and_deduplicate_urls(user_text)
    render_valid_url_feedback(urls)
    render_invalid_url_section(bad)

    body = {"inputs": urls}
    attach_openai_config(config, body)  # adds optional LLM + credentials if safe

    items, skipped, duration = parse_job_result(job)
    summarize_results(items, skipped, start_time)

Notes:
- Inline credential attachment is *conditional*: masked values are detected and omitted.
- `parse_job_result` preserves dynamic fields by avoiding schema coercion when possible.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from enum import Enum
from typing import TYPE_CHECKING, Any

import streamlit as st

from agentic_scraper.backend.config.constants import REQUIRED_CONFIG_FIELDS_FOR_LLM
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_CACHE_DECISION,
    MSG_DEBUG_LLM_FIELDS_ATTACHED,
    MSG_DEBUG_PARSE_RESULT_SUMMARY,
    MSG_DEBUG_PIPELINE_INPUT,
    MSG_DEBUG_RESPONSE_BODY_COMPACT,
    MSG_ERROR_JOB_FAILED,
    MSG_INFO_INLINE_KEY_MASKED_FALLBACK,
    MSG_INFO_JOB_CANCELED,
    MSG_INFO_NO_RESULTS,
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

# Cosmetic domain → emoji mapping for quick visual scanning in results.
DOMAIN_EMOJIS = {
    "youtube.com": "🎮",
    "github.com": "💻",
    "amazon.com": "🎭",
    "medium.com": "✍️",
    "wikipedia.org": "📚",
    "google.com": "🔎",
}

# Heuristic mask detection for inline secret override avoidance.
MASK_CHARS: set[str] = {"*", "•", "●", "·"}
MASK_WORDS: set[str] = {"redacted", "masked", "hidden"}

# Truncation limit for debug/preview logs.
PREVIEW_LIMIT = 10


def _looks_masked(s: str | None) -> bool:
    """
    Heuristically detect redacted/masked secrets.

    Flags common mask characters (*, •, ●, ·) or placeholder words.

    Args:
        s (str | None): Candidate value to inspect.

    Returns:
        bool: True if the value appears masked; False otherwise.

    Examples:
        _looks_masked("sk-****abcd")  # -> True
        _looks_masked("sk-live-xyz")  # -> False
    """
    if not isinstance(s, str) or not s:
        return False
    if any(ch in s for ch in MASK_CHARS):
        return True
    ls = s.lower()
    return any(w in ls for w in MASK_WORDS)


def validate_and_deduplicate_urls(raw_input: str) -> tuple[list[str], list[str]]:
    """
    Clean and deduplicate user input URLs, separating valid from invalid lines.

    Process:
        1) Split non-empty lines and trim whitespace.
        2) Use `clean_input_urls` to filter valid URLs.
        3) Anything not in the valid set is considered invalid.
        4) Deduplicate valid URLs via `deduplicate_urls`.

    Args:
        raw_input (str): The raw multi-line user input.

    Returns:
        tuple[list[str], list[str]]: (`deduped_valid_urls`, `invalid_lines`)

    Examples:
        valid, invalid = validate_and_deduplicate_urls("https://a.com\\nnot-a-url")
        # valid  -> ["https://a.com"]
        # invalid-> ["not-a-url"]

    Notes:
        - Debug logs summarize counts and include a truncated preview of invalid lines.
    """
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
    """
    Return an emoji icon representing a known domain (cosmetic helper).

    Args:
        url (str): The URL string.

    Returns:
        str: A representative emoji or a default link icon.

    Examples:
        extract_domain_icon("https://github.com")  # -> "💻"
        extract_domain_icon("https://unknown.tld") # -> "🔗"
    """
    for domain, emoji in DOMAIN_EMOJIS.items():
        if domain in url:
            return emoji
    return "🔗"


def summarize_results(items: Sequence[Mapping[str, Any]], skipped: int, start_time: float) -> None:
    """
    Display scraping performance metrics and a quick view of results.

    Args:
        items (Sequence[Mapping[str, Any]]): Extracted items (already plain dict-like).
        skipped (int): Number of inputs that failed or were skipped.
        start_time (float): A perf_counter timestamp taken at job start.

    Returns:
        None

    Notes:
        - Adds a short metrics header and a compact list of extracted URLs (with emojis).
        - Emits a debug decision log when no items are present.
    """
    elapsed = round(time.perf_counter() - start_time, 2)

    if not items:
        st.warning(MSG_INFO_NO_RESULTS)
        with suppress(Exception):
            key = f"skipped={skipped} elapsed={elapsed}"
            logger.debug(MSG_DEBUG_CACHE_DECISION.format(decision="NO_ITEMS", key=key))
        return

    st.markdown("## 🎉 Extraction Complete")
    col1, col2, col3 = st.columns(3)
    col1.metric("✅ Extracted", f"{len(items)} URLs")
    col2.metric("⚠️ Skipped", f"{skipped} URLs")
    col3.metric("⏱️ Time", f"{elapsed:.2f}s")
    st.caption(
        "Includes job metadata, stats, and raw results. "
        "For table-only exports, see the Results tab."
    )
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
    """
    Show an expandable UI section listing invalid input URLs.

    Args:
        invalid_lines (list[str]): Lines from user input that did not parse as URLs.

    Returns:
        None

    Notes:
        - Traces invalid count via debug logs; list is fully rendered in the expander.
    """
    if invalid_lines:
        with suppress(Exception):
            body = f"invalid_count={len(invalid_lines)}"
            logger.debug(MSG_DEBUG_RESPONSE_BODY_COMPACT.format(body=body))
        with st.expander("⚠️ Skipped Invalid URLs"):
            for url in invalid_lines:
                st.markdown(f"- ❌ `{url}` — *invalid URL format*")


def render_valid_url_feedback(urls: list[str]) -> None:
    """
    Show sidebar/body feedback when valid URLs are detected.

    Args:
        urls (list[str]): Valid, deduplicated URLs.

    Returns:
        None

    Notes:
        - Stores the validated list on `st.session_state.valid_urls` for downstream usage.
        - Emits a compact debug log with valid count.
    """
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
    Attach inline OpenAI credentials and LLM params to a job request body.

    Rules:
        - If the local session holds *unmasked* credentials, attach them as
          `body["openai_credentials"] = {...}` to override stored backend creds.
        - If the local key appears masked or missing, **do not** attach, letting
          the backend fall back to stored credentials (logs an info message).
        - Always attach LLM parameters (`openai_model`, `llm_concurrency`, `llm_schema_retries`)
          when present in the `config`.

    Args:
        config (PipelineConfig): Current UI config/state to pull LLM params from.
        body (dict[str, Any]): The outbound request payload to mutate.

    Returns:
        bool: Always True (the body is mutated in-place).

    Examples:
        body = {"inputs": urls}
        attach_openai_config(config, body)

    Notes:
        - This function avoids writing masked/unusable secrets to the request.
        - A debug log lists which LLM-related fields were attached.
    """
    openai_credentials = st.session_state.get("openai_credentials")

    # Normalize creds payload (Pydantic v2 model or plain mapping)
    creds_payload: dict[str, Any] | None = None
    if openai_credentials is not None:
        dump = getattr(openai_credentials, "model_dump", None)
        if callable(dump):
            creds_payload = dump()
        elif isinstance(openai_credentials, Mapping):
            creds_payload = dict(openai_credentials)

    # Attach inline creds only if present and not masked
    if creds_payload:
        api_key = creds_payload.get("api_key")
        if isinstance(api_key, str) and api_key and not _looks_masked(api_key):
            body["openai_credentials"] = creds_payload
        else:
            logger.info(MSG_INFO_INLINE_KEY_MASKED_FALLBACK)

    # Attach optional LLM params from config
    openai_model = getattr(config, "openai_model", None)
    llm_concurrency = getattr(config, "llm_concurrency", None)
    llm_schema_retries = getattr(config, "llm_schema_retries", None)

    if openai_model is not None:
        body["openai_model"] = (
            openai_model.value if isinstance(openai_model, Enum) else openai_model
        )
    if llm_concurrency is not None:
        body["llm_concurrency"] = llm_concurrency
    if llm_schema_retries is not None:
        body["llm_schema_retries"] = llm_schema_retries

    # Debug which fields we actually attached (sourced from REQUIRED_CONFIG_FIELDS_FOR_LLM).
    fields = [k for k in REQUIRED_CONFIG_FIELDS_FOR_LLM if k in body]
    logger.debug(MSG_DEBUG_LLM_FIELDS_ATTACHED.format(fields=fields))

    return True


# -------------------------
# New helpers for job-based flow
# -------------------------
def parse_job_result(job: dict[str, Any]) -> tuple[list[dict[str, Any]], int, float]:
    """
    Convert a final job payload (status == 'succeeded') into plain dict items + stats.

    Args:
        job (dict[str, Any]): Final job payload (should contain `result` with `items` and `stats`).

    Returns:
        tuple[list[dict[str, Any]], int, float]: (`items`, `skipped`, `duration_sec`)
            - `items`: `list[dict[str, Any]]` with ALL fields preserved (including dynamic extras).
            - `skipped`: Count of failed items (`stats.num_failed`).
            - `duration_sec`: Job wall-clock duration in seconds (`stats.duration_sec`).

    Notes:
        - Items that are already dicts are preserved as-is.
        - For Pydantic-like objects, `model_dump()` / `dict()` is used to produce a plain dict.
        - Unexpected types or attribute errors are warned and skipped (with UI + log).
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
    """
    Render a terminal job error or cancellation message in the UI.

    Args:
        job (dict[str, Any]): Final job payload that includes `status` and optional `error`.

    Returns:
        None

    Notes:
        - If canceled, shows a friendly info message.
        - If failed, renders an error from `error.message` when available; otherwise a fallback.
    """
    status_ = (job.get("status") or "").lower()
    if status_ == "canceled":
        st.info(MSG_INFO_JOB_CANCELED)
        return

    err = job.get("error")
    if isinstance(err, dict) and "message" in err:
        msg = err.get("message")
    else:
        msg = str(err) if err else MSG_ERROR_JOB_FAILED
    with suppress(Exception):
        logger.warning(MSG_DEBUG_RESPONSE_BODY_COMPACT.format(body=f"job_error={msg}"))
    st.error(msg)
