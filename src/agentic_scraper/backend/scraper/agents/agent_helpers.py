"""
Shared utility functions for LLM-based scraping agents in AgenticScraper.

"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from openai import APIError, OpenAIError, RateLimitError
from playwright.async_api import Error as PlaywrightError
from pydantic import ValidationError

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_API_EXCEPTION,
    MSG_DEBUG_CONTEXT_HINTS_EXTRACTED,
    MSG_DEBUG_EARLY_EXIT_SKIPPED,
    MSG_DEBUG_EARLY_EXIT_TRIGGERED,
    MSG_DEBUG_LLM_FIELD_SCORE_DETAILS,
    MSG_DEBUG_LLM_JSON_DUMP_SAVED,
    MSG_DEBUG_PARSED_STRUCTURED_DATA,
    MSG_DEBUG_USING_BEST_CANDIDATE_FIELDS,
    MSG_ERROR_API,
    MSG_ERROR_API_LOG_WITH_URL,
    MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL,
    MSG_ERROR_MASKED_OPENAI_API_KEY,
    MSG_ERROR_MISSING_OPENAI_API_KEY,
    MSG_ERROR_MISSING_OPENAI_CONFIG,
    MSG_ERROR_MISSING_OPENAI_PROJECT_ID,
    MSG_ERROR_OPENAI_UNEXPECTED,
    MSG_ERROR_OPENAI_UNEXPECTED_LOG_WITH_URL,
    MSG_ERROR_RATE_LIMIT_DETAIL,
    MSG_ERROR_RATE_LIMIT_LOG_WITH_URL,
    MSG_ERROR_SCREENSHOT_FAILED_WITH_URL,
    MSG_INFO_ADAPTIVE_EXTRACTION_SUCCESS_WITH_URL,
)
from agentic_scraper.backend.scraper.agents.field_utils import (
    FIELD_WEIGHTS,
    score_nonempty_fields,
)
from agentic_scraper.backend.scraper.schemas import ScrapedItem
from agentic_scraper.backend.scraper.screenshotter import capture_screenshot

if TYPE_CHECKING:
    from agentic_scraper.backend.config.types import OpenAIConfig
    from agentic_scraper.backend.core.settings import Settings

logger = logging.getLogger(__name__)

__all__ = [
    "capture_optional_screenshot",
    "extract_context_hints",
    "handle_openai_exception",
    "log_structured_data",
    "retrieve_openai_credentials",
    "score_and_log_fields",
    "try_validate_scraped_item",
]

# ---------------------------------------------------------------------------
# Secret masking detection (defense-in-depth)
# ---------------------------------------------------------------------------

MASK_CHARS: set[str] = {"*", "•", "●", "·"}
MASK_WORDS: set[str] = {"redacted", "masked", "hidden"}


def _is_masked_secret(s: str | None) -> bool:
    """Return True if the string looks redacted/masked."""
    if not isinstance(s, str) or not s:
        return False
    if any(ch in s for ch in MASK_CHARS):
        return True
    ls = s.lower()
    return any(w in ls for w in MASK_WORDS)


# ─────────────────────────────────────────────────────────────────────────────
# Screenshot & OpenAI exception handling
# ─────────────────────────────────────────────────────────────────────────────


async def capture_optional_screenshot(url: str, settings: Settings) -> str | None:
    """
    Attempt to capture a screenshot of the URL. Logs errors and returns None on failure.
    """
    try:
        return await capture_screenshot(url, output_dir=Path(settings.screenshot_dir))
    except (PlaywrightError, OSError, ValueError):
        logger.warning(MSG_ERROR_SCREENSHOT_FAILED_WITH_URL.format(url=url))
        return None


def handle_openai_exception(e: OpenAIError, url: str, settings: Settings) -> None:
    """
    Log and handle OpenAI-related errors with verbosity-aware logging.
    """
    if isinstance(e, RateLimitError):
        logger.warning(MSG_ERROR_RATE_LIMIT_LOG_WITH_URL.format(url=url))
        if settings.is_verbose_mode:
            logger.debug(MSG_ERROR_RATE_LIMIT_DETAIL.format(error=e))
    elif isinstance(e, APIError):
        logger.warning(MSG_ERROR_API_LOG_WITH_URL.format(url=url))
        if settings.is_verbose_mode:
            logger.debug(MSG_DEBUG_API_EXCEPTION)
            logger.debug(MSG_ERROR_API.format(error=e))
    else:
        logger.warning(MSG_ERROR_OPENAI_UNEXPECTED_LOG_WITH_URL.format(url=url))
        if settings.is_verbose_mode:
            logger.debug(MSG_ERROR_OPENAI_UNEXPECTED.format(error=e))


# ─────────────────────────────────────────────────────────────────────────────
# Logging and debugging utilities
# ─────────────────────────────────────────────────────────────────────────────


def log_structured_data(data: dict[str, Any], settings: Settings) -> None:
    """
    Log a summary of structured LLM-extracted data, and optionally dump full JSON.
    """
    if not settings.is_verbose_mode:
        return

    summary = {
        k: f"str({len(v)})" if isinstance(v, str) else "None" if v is None else type(v).__name__
        for k, v in data.items()
    }
    logger.debug(MSG_DEBUG_PARSED_STRUCTURED_DATA.format(data=summary))

    if settings.dump_llm_json_dir:
        dump_dir = Path(settings.dump_llm_json_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=timezone.utc).isoformat().replace(":", "_")
        filename = f"{timestamp}.json"
        dump_path = dump_dir / filename
        with dump_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.debug(MSG_DEBUG_LLM_JSON_DUMP_SAVED.format(path=str(dump_path)))


# ─────────────────────────────────────────────────────────────────────────────
# LLM prompt context extraction
# ─────────────────────────────────────────────────────────────────────────────


def extract_context_hints(html: str, url: str) -> dict[str, str]:
    """
    Extract contextual hints from the HTML and URL for better LLM prompt construction.
    """
    soup = BeautifulSoup(html, "html.parser")

    useful_meta_keys = {
        "title",
        "description",
        "keywords",
        "author",
        "og:title",
        "og:description",
        "og:site_name",
        "og:type",
        "article:published_time",
        "twitter:title",
        "twitter:description",
    }
    meta_tags = {
        k: v
        for tag in soup.find_all("meta")
        if (
            (k := tag.get("name") or tag.get("property")) in useful_meta_keys
            and (v := tag.get("content"))
        )
    }
    meta_summary = "; ".join(f"{k}={v}" for k, v in meta_tags.items())

    breadcrumb_selectors = [
        '[class*="breadcrumb"]',
        '[id*="breadcrumb"]',
        '[class*="breadcrumbs"]',
        '[id*="breadcrumbs"]',
    ]
    breadcrumb_texts: list[str] = []
    seen_breadcrumbs = set()
    for sel in breadcrumb_selectors:
        for elem in soup.select(sel):
            text = elem.get_text(strip=True)
            if text and text not in seen_breadcrumbs:
                breadcrumb_texts.append(text)
                seen_breadcrumbs.add(text)

    if not breadcrumb_texts:
        nav_breadcrumb = soup.select_one("nav[aria-label='breadcrumb']")
        if nav_breadcrumb:
            breadcrumb_texts.append(nav_breadcrumb.get_text(strip=True))

    breadcrumbs = " > ".join(breadcrumb_texts)
    parsed = urlparse(url)
    url_segments = " / ".join(filter(None, parsed.path.split("/")))
    domain = parsed.netloc.lower()
    last_segment = parsed.path.rstrip("/").split("/")[-1]

    page_title = soup.title.string.strip() if soup.title and soup.title.string else ""
    h1 = soup.find("h1")
    first_h1 = h1.get_text(strip=True) if h1 else ""

    # Naive page type inference
    lower_url = url.lower()
    lower_title = page_title.lower()
    lower_h1 = first_h1.lower()
    combined = f"{lower_url} {lower_title} {lower_h1}"

    if "product" in combined or "shop" in combined:
        page_type = "product"
    elif "job" in combined or "career" in combined or "apply" in combined:
        page_type = "job"
    elif "blog" in combined or "post" in combined or "article" in combined:
        page_type = "blog"
    else:
        page_type = "unknown"

    logger.debug(
        MSG_DEBUG_CONTEXT_HINTS_EXTRACTED.format(
            url=url,
            page_type=page_type,
            meta_keys=len(meta_tags),
            breadcrumbs=len(breadcrumb_texts),
        )
    )
    return {
        "meta": meta_summary,
        "breadcrumbs": breadcrumbs,
        "url_segments": url_segments,
        "context_domain": domain,
        "url_last_segment": last_segment,
        "page_title": page_title,
        "first_h1": first_h1,
        "page": page_type,  # used by prompt_helpers.py
    }


# ─────────────────────────────────────────────────────────────────────────────
# Data validation and scoring
# ─────────────────────────────────────────────────────────────────────────────


def try_validate_scraped_item(
    data: dict[str, Any], url: str, settings: Settings
) -> ScrapedItem | None:
    """
    Attempt to validate the scraped data against the ScrapedItem schema.
    """
    if not data:
        return None

    try:
        item = ScrapedItem.model_validate(data)
    except ValidationError as ve:
        logger.warning(MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL.format(url=url, exc=ve))
        return None
    else:
        logger.info(MSG_INFO_ADAPTIVE_EXTRACTION_SUCCESS_WITH_URL.format(url=url))
        logger.debug(MSG_DEBUG_USING_BEST_CANDIDATE_FIELDS.format(fields=list(data.keys())))
        log_structured_data(item.model_dump(mode="json"), settings)
        return item


def score_and_log_fields(
    fields: set[str],
    attempt: int,
    url: str,
    raw_data: dict[str, Any] | None = None,
) -> float:
    """
    Compute a weighted score for non-empty fields and log details for debugging.
    """
    nonempty_keys = {
        k
        for k, v in (raw_data.items() if raw_data else [(f, "nonempty") for f in fields])
        if v not in [None, ""]
    }

    score = score_nonempty_fields(raw_data or dict.fromkeys(nonempty_keys, "nonempty"))

    logger.debug(
        MSG_DEBUG_LLM_FIELD_SCORE_DETAILS.format(
            attempt=attempt,
            url=url,
            score=score,
            field_weights={k: FIELD_WEIGHTS.get(k, 0.3) for k in nonempty_keys},
        )
    )

    return score


def retrieve_openai_credentials(config: OpenAIConfig | None) -> tuple[str, str]:
    """
    Validate and extract OpenAI credentials from the config.

    Returns:
        (api_key, project_id)
    """
    if config is None:
        raise ValueError(MSG_ERROR_MISSING_OPENAI_CONFIG)
    if not config.api_key:
        raise ValueError(MSG_ERROR_MISSING_OPENAI_API_KEY)
    # Defensive: refuse obviously masked keys
    if _is_masked_secret(config.api_key):
        raise ValueError(MSG_ERROR_MASKED_OPENAI_API_KEY)
    if not config.project_id:
        raise ValueError(MSG_ERROR_MISSING_OPENAI_PROJECT_ID)
    return config.api_key, config.project_id


# (Optional, still available if other agents import it)
def should_exit_early(
    *,
    item: ScrapedItem | None,
    raw_data: dict[str, Any],
    best_fields: dict[str, Any] | None,
    missing: set[str],
    url: str,
) -> bool:
    """
    Decide whether to stop retrying based on whether any useful progress was made.
    """
    if item is None:
        return False
    if not best_fields:
        return False

    previous_keys = set(best_fields)
    current_keys = set(raw_data)
    new_fields = current_keys - previous_keys
    newly_filled_missing = missing & new_fields

    should_stop = not new_fields and not newly_filled_missing

    if should_stop:
        logger.debug(MSG_DEBUG_EARLY_EXIT_TRIGGERED.format(url=url))
    else:
        logger.debug(
            MSG_DEBUG_EARLY_EXIT_SKIPPED.format(
                url=url,
                new_fields=new_fields,
                newly_filled_missing=newly_filled_missing,
            )
        )

    return should_stop
