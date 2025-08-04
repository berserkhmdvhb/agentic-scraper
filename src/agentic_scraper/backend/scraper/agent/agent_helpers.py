"""
Shared utility functions for LLM-based scraping agents in AgenticScraper.

This module provides reusable helpers to support adaptive and static scraping agents.
It includes functionality for:
- Parsing and validating LLM JSON output
- Structured error logging (OpenAI, decoding, validation)
- Screenshot capture for debugging
- Extraction of contextual hints from HTML
- Scoring and selecting retry candidates for adaptive extraction

Used primarily by llm_dynamic.py, llm_dynamic_adaptive.py, and related agents.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from openai import APIError, OpenAIError, RateLimitError
from playwright.async_api import Error as PlaywrightError
from pydantic import ValidationError

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_API_EXCEPTION,
    MSG_DEBUG_LLM_FIELD_SCORE_DETAILS,
    MSG_DEBUG_LLM_JSON_DUMP_SAVED,
    MSG_DEBUG_PARSED_STRUCTURED_DATA,
    MSG_DEBUG_USING_BEST_CANDIDATE_FIELDS,
    MSG_ERROR_API,
    MSG_ERROR_API_LOG_WITH_URL,
    MSG_ERROR_JSON_DECODING_FAILED_WITH_URL,
    MSG_ERROR_LLM_JSON_DECODE_LOG,
    MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL,
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
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.agent.field_utils import FIELD_WEIGHTS, score_nonempty_fields
from agentic_scraper.backend.scraper.models import OpenAIConfig, ScrapedItem
from agentic_scraper.backend.scraper.screenshotter import capture_screenshot

logger = logging.getLogger(__name__)

__all__ = [
    "capture_optional_screenshot",
    "extract_context_hints",
    "handle_openai_exception",
    "log_structured_data",
    "parse_llm_response",
    "retrieve_openai_credentials",
    "score_and_log_fields",
    "try_validate_scraped_item",
]

# ─────────────────────────────────────────────────────────────────────────────
# Low-level helpers: JSON parsing, screenshot, exception handling
# ─────────────────────────────────────────────────────────────────────────────


def parse_llm_response(content: str, url: str, settings: Settings) -> dict[str, Any] | None:
    """
    Safely parse LLM JSON content. Logs errors and returns None on failure.

    Args:
        content (str): JSON string returned by the LLM.
        url (str): The source URL being processed.
        settings (Settings): Runtime config controlling verbosity and error logging.

    Returns:
        dict[str, Any] | None: Parsed dictionary if successful, else None.

    Raises:
        None
    """
    try:
        return cast("dict[str, Any]", json.loads(content))
    except json.JSONDecodeError as e:
        logger.warning(MSG_ERROR_JSON_DECODING_FAILED_WITH_URL.format(exc=e, url=url))
        if settings.is_verbose_mode:
            logger.debug(MSG_ERROR_LLM_JSON_DECODE_LOG.format(exc=e, url=url))
        return None


async def capture_optional_screenshot(url: str, settings: Settings) -> str | None:
    """
    Attempt to capture a screenshot of the URL. Logs errors and returns None on failure.

    Args:
        url (str): The URL to screenshot.
        settings (Settings): Runtime config including screenshot path.

    Returns:
        str | None: Path to saved screenshot if successful, otherwise None.

    Raises:
        None
    """
    try:
        return await capture_screenshot(url, output_dir=Path(settings.screenshot_dir))
    except (PlaywrightError, OSError, ValueError):
        logger.warning(MSG_ERROR_SCREENSHOT_FAILED_WITH_URL.format(url=url))
        return None


def handle_openai_exception(e: OpenAIError, url: str, settings: Settings) -> None:
    """
    Log and handle OpenAI-related errors with verbosity-aware logging.

    Args:
        e (OpenAIError): The OpenAI exception raised.
        url (str): The URL that triggered the exception.
        settings (Settings): Runtime config for verbosity.

    Returns:
        None

    Raises:
        None
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

    Args:
        data (dict[str, Any]): Validated structured data from the LLM.
        settings (Settings): Runtime config (controls verbose mode and JSON dump).

    Returns:
        None

    Raises:
        None
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

    Args:
        html (str): Raw HTML content of the page.
        url (str): Source URL of the page.

    Returns:
        dict[str, str]: Dictionary of contextual elements (meta tags, breadcrumbs, segments, etc.).

    Raises:
        None
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

    # ─── Naive Page Type Inference ─────────────────────────────────────────────
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

    return {
        "meta": meta_summary,
        "breadcrumbs": breadcrumbs,
        "url_segments": url_segments,
        "context_domain": domain,
        "url_last_segment": last_segment,
        "page_title": page_title,
        "first_h1": first_h1,
        "page": page_type,  # Included for prompt_helpers.py
    }


# ─────────────────────────────────────────────────────────────────────────────
# Data validation and retry scoring
# ─────────────────────────────────────────────────────────────────────────────


def try_validate_scraped_item(
    data: dict[str, Any], url: str, settings: Settings
) -> ScrapedItem | None:
    """
    Attempt to validate the scraped data against the ScrapedItem schema.

    Args:
        data (dict[str, Any]): Raw JSON-like dict from LLM output.
        url (str): The URL where the data came from.
        settings (Settings): Runtime config used for logging.

    Returns:
        ScrapedItem | None: Validated item or None if validation failed.
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

    Args:
        config (OpenAIConfig | None): The OpenAI credentials configuration.

    Returns:
        tuple[str, str]: A tuple of (api_key, project_id).

    Raises:
        ValueError: If config is None or required fields are missing.
    """
    if config is None:
        raise ValueError(MSG_ERROR_MISSING_OPENAI_CONFIG)
    if not config.api_key:
        raise ValueError(MSG_ERROR_MISSING_OPENAI_API_KEY)
    if not config.project_id:
        raise ValueError(MSG_ERROR_MISSING_OPENAI_PROJECT_ID)
    return config.api_key, config.project_id
