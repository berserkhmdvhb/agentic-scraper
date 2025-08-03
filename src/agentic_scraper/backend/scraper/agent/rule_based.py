"""
Rule-based scraping agent for extracting structured data using regex heuristics.

This module implements a lightweight fallback agent that infers fields like
title, description, and price using simple text and regex rules, rather than LLMs.
It is used when LLM usage is disabled or unavailable.

Key Features:
- Uses regular expressions to detect price patterns.
- Extracts first non-empty line as title.
- Extracts a medium-length paragraph as description.
- Optionally captures a screenshot via Playwright.
- Returns a validated `ScrapedItem`, or None if validation fails.

Used in: scraper agent registry when `agent_mode="rule_based"` is selected.
"""

import logging
import re

from pydantic import ValidationError

from agentic_scraper.backend.scraper.agent.agent_helpers import (
    capture_optional_screenshot,
    log_structured_data,
)
from agentic_scraper.config.constants import (
    DESCRIPTION_MAX_LENGTH,
    DESCRIPTION_MIN_LENGTH,
    REGEX_PARAGRAPH_SPLIT_PATTERN,
    REGEX_PRICE_PATTERN,
)
from agentic_scraper.config.messages import (
    MSG_DEBUG_RULE_BASED_DESCRIPTION,
    MSG_DEBUG_RULE_BASED_PRICE,
    MSG_DEBUG_RULE_BASED_START,
    MSG_DEBUG_RULE_BASED_TITLE,
    MSG_DEBUG_RULE_BASED_VALIDATION_FAILED_FIELDS,
    MSG_DEBUG_RULE_BASED_VALIDATION_SUCCESS,
    MSG_ERROR_RULE_BASED_EXTRACTION_FAILED,
)
from agentic_scraper.config.models import ScrapedItem, ScrapeRequest
from agentic_scraper.core.settings import Settings

__all__ = ["extract_structured_data"]

logger = logging.getLogger(__name__)


def guess_price(text: str) -> float | None:
    """
    Extract the first detected price-like pattern from the input text.

    Args:
        text (str): The full text content of the webpage.

    Returns:
        float | None: Parsed price value, or None if not found or invalid.
    """
    price_match = re.search(REGEX_PRICE_PATTERN, text)
    if price_match:
        try:
            return float(price_match.group(1).replace(",", "."))
        except ValueError:
            return None
    return None


def guess_title(text: str) -> str | None:
    """
    Extract the first non-empty line from the input text as a potential title.

    Args:
        text (str): The full text content of the webpage.

    Returns:
        str | None: Title candidate, or None if no valid line found.
    """
    for line in text.strip().splitlines():
        clean = line.strip()
        if clean:
            return clean
    return None


def guess_description(text: str) -> str | None:
    """
    Extract a paragraph of medium length from the text as a description.

    Args:
        text (str): The full text content of the webpage.

    Returns:
        str | None: A paragraph matching the length constraints, or None if not found.
    """
    paragraphs = re.split(REGEX_PARAGRAPH_SPLIT_PATTERN, text)
    for p in paragraphs:
        clean = p.strip()
        if DESCRIPTION_MIN_LENGTH <= len(clean) <= DESCRIPTION_MAX_LENGTH:
            return clean
    return None


async def extract_structured_data(
    request: ScrapeRequest,
    *,
    settings: Settings,
) -> ScrapedItem | None:
    """
    Perform rule-based extraction of structured data from a scrape request.

    This function infers common metadata fields using simple regex or text-based
    heuristics and returns a validated `ScrapedItem`. It also logs intermediate
    values and optionally captures a screenshot.

    Args:
        request (ScrapeRequest): The incoming URL and cleaned page content.
        settings (Settings): Runtime configuration including screenshot flag.

    Returns:
        ScrapedItem | None: Structured result if valid, otherwise None.

    Raises:
        None explicitly. Validation errors are logged and handled gracefully.
    """
    title = guess_title(request.text)
    description = guess_description(request.text)
    price = guess_price(request.text)
    screenshot_path: str | None = None

    logger.debug(MSG_DEBUG_RULE_BASED_START.format(url=request.url))
    logger.debug(MSG_DEBUG_RULE_BASED_TITLE.format(title=title))
    logger.debug(MSG_DEBUG_RULE_BASED_DESCRIPTION.format(description=description))
    logger.debug(MSG_DEBUG_RULE_BASED_PRICE.format(price=price))

    if request.take_screenshot:
        screenshot_path = await capture_optional_screenshot(request.url, settings)

    log_structured_data(
        {
            "title": title,
            "description": description,
            "price": price,
            "author": None,
            "date_published": None,
            "screenshot_path": screenshot_path,
        },
        settings,
    )

    try:
        item = ScrapedItem(
            url=request.url,
            title=title,
            description=description,
            price=price,
            author=None,
            date_published=None,
            screenshot_path=screenshot_path,
        )
    except ValidationError:
        logger.exception(MSG_ERROR_RULE_BASED_EXTRACTION_FAILED.format(url=request.url))
        logger.debug(
            MSG_DEBUG_RULE_BASED_VALIDATION_FAILED_FIELDS.format(
                title=title,
                description=description,
                price=price,
                url=request.url,
            )
        )
        return None
    else:
        logger.debug(MSG_DEBUG_RULE_BASED_VALIDATION_SUCCESS)
        return item
