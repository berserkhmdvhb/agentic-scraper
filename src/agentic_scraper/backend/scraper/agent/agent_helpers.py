import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from openai import APIError, OpenAIError, RateLimitError
from playwright.async_api import Error as PlaywrightError

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_API_EXCEPTION,
    MSG_DEBUG_LLM_JSON_DUMP_SAVED,
    MSG_DEBUG_PARSED_STRUCTURED_DATA,
    MSG_ERROR_API,
    MSG_ERROR_API_LOG_WITH_URL,
    MSG_ERROR_JSON_DECODING_FAILED_WITH_URL,
    MSG_ERROR_LLM_JSON_DECODE_LOG,
    MSG_ERROR_OPENAI_UNEXPECTED,
    MSG_ERROR_OPENAI_UNEXPECTED_LOG_WITH_URL,
    MSG_ERROR_RATE_LIMIT_DETAIL,
    MSG_ERROR_RATE_LIMIT_LOG_WITH_URL,
    MSG_ERROR_SCREENSHOT_FAILED_WITH_URL,
)
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.screenshotter import capture_screenshot

logger = logging.getLogger(__name__)


def parse_llm_response(content: str, url: str, settings: Settings) -> dict[str, Any] | None:
    """
    Safely parse LLM JSON content. Logs errors and returns None on failure.
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
    Try to capture a screenshot. Logs any failure and returns None.
    """
    try:
        return await capture_screenshot(url, output_dir=Path(settings.screenshot_dir))
    except (PlaywrightError, OSError, ValueError):
        logger.warning(MSG_ERROR_SCREENSHOT_FAILED_WITH_URL.format(url=url))
        return None


def handle_openai_exception(e: OpenAIError, url: str, settings: Settings) -> None:
    """
    Log structured errors from OpenAI exceptions with optional verbose detail.
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


def log_structured_data(data: dict[str, Any], settings: Settings) -> None:
    if not settings.is_verbose_mode:
        return

    # Log summary only
    summary = {
        k: f"str({len(v)})" if isinstance(v, str) else "None" if v is None else type(v).__name__
        for k, v in data.items()
    }
    logger.debug(MSG_DEBUG_PARSED_STRUCTURED_DATA.format(data=summary))

    # Optionally dump full JSON to a file (guarded by a setting)
    if settings.dump_llm_json_dir:
        dump_dir = Path(settings.dump_llm_json_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=timezone.utc).isoformat().replace(":", "_")
        filename = f"{timestamp}.json"
        dump_path = dump_dir / filename
        with dump_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.debug(MSG_DEBUG_LLM_JSON_DUMP_SAVED.format(path=str(dump_path)))


def extract_context_hints(html: str, url: str) -> dict[str, str]:
    """
    Extract contextual hints from HTML and URL for LLM prompting:
    - Useful meta tags (title, description, etc.)
    - Breadcrumbs (deduplicated)
    - URL segments and page type hint
    - Domain name (for prompt adaptation)
    - Optional enhancements: <title> and <h1>
    """

    soup = BeautifulSoup(html, "html.parser")

    # Useful meta tags only
    useful_meta_keys = {
        "title", "description", "keywords", "author",
        "og:title", "og:description", "og:site_name", "og:type",
        "article:published_time", "twitter:title", "twitter:description",
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

    # Breadcrumbs
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

    # Fallback breadcrumb detection
    if not breadcrumb_texts:
        nav_breadcrumb = soup.select_one("nav[aria-label='breadcrumb']")
        if nav_breadcrumb:
            breadcrumb_texts.append(nav_breadcrumb.get_text(strip=True))

    breadcrumbs = " > ".join(breadcrumb_texts)

    # URL-based hints
    parsed = urlparse(url)
    url_segments = " / ".join(filter(None, parsed.path.split("/")))
    domain = parsed.netloc.lower()
    last_segment = parsed.path.rstrip("/").split("/")[-1]

    # Optional extra context
    page_title = soup.title.string.strip() if soup.title and soup.title.string else ""
    h1 = soup.find("h1")
    first_h1 = h1.get_text(strip=True) if h1 else ""

    return {
        "meta": meta_summary,
        "breadcrumbs": breadcrumbs,
        "url_segments": url_segments,
        "context_domain": domain,
        "page_hint": last_segment,
        "page_title": page_title,
        "first_h1": first_h1,
    }
