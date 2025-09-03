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

Used in: scraper agent registry when `agent_mode=AgentMode.RULE_BASED` is selected.
"""

import logging
import re

from pydantic import ValidationError

from agentic_scraper.backend.config.constants import (
    DESCRIPTION_MAX_LENGTH,
    DESCRIPTION_MIN_LENGTH,
    REGEX_PARAGRAPH_SPLIT_PATTERN,
    REGEX_PRICE_PATTERN,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_RULE_BASED_DESCRIPTION,
    MSG_DEBUG_RULE_BASED_PRICE,
    MSG_DEBUG_RULE_BASED_START,
    MSG_DEBUG_RULE_BASED_TITLE,
    MSG_DEBUG_RULE_BASED_VALIDATION_FAILED_FIELDS,
    MSG_DEBUG_RULE_BASED_VALIDATION_SUCCESS,
    MSG_ERROR_RULE_BASED_EXTRACTION_FAILED,
    MSG_WARN_RULE_BASED_NO_FIELDS,
)
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.agents.agent_helpers import (
    capture_optional_screenshot,
    log_structured_data,
)
from agentic_scraper.backend.scraper.models import ScrapeRequest
from agentic_scraper.backend.scraper.schemas import ScrapedItem

__all__ = ["extract_structured_data"]

logger = logging.getLogger(__name__)

MIN_GROUPS_FOR_DECIMAL = 2
TAIL_WINDOW = 6
_FALLBACK_NUM_THEN_CURR = re.compile(r"(\d{1,3}(?:[.,]\d{3})*[.,]?\d{1,4})\s*[€$]")
_FALLBACK_CURR_THEN_NUM = re.compile(r"[€$]\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]?\d{1,4})?)")


# helpers kept local to this module


def _search_price_match(text: str) -> re.Match[str] | None:
    """
    Try the main project pattern, then common currency/number fallbacks.
    """
    m = re.search(REGEX_PRICE_PATTERN, text)
    if m:
        return m
    return _FALLBACK_NUM_THEN_CURR.search(text) or _FALLBACK_CURR_THEN_NUM.search(text)


def _best_candidate_from_match(m: re.Match[str], text: str) -> str | None:
    """
    From a regex match, choose the most price-like string, optionally
    synthesizing decimals from groups or a trailing fractional tail.
    """
    groups = [g for g in (m.groups() or ()) if g]
    candidates = [*groups, m.group(0)]

    def _score(s: str) -> tuple[int, int, int]:
        has_sep = 1 if ("," in s or "." in s) else 0
        digit_count = sum(ch.isdigit() for ch in s)
        return (has_sep, digit_count, len(s))

    best = max(candidates, key=_score)

    # If groups look like integer + fraction without a separator, synthesize one.
    if len(groups) >= MIN_GROUPS_FOR_DECIMAL and ("." not in best and "," not in best):
        combined = f"{groups[0]}.{groups[1]}"
        best = max([*candidates, combined], key=_score)

    # If we still lack a separator, peek right after the match for a fractional tail.
    if "." not in best and "," not in best:
        tail = text[m.end() : m.end() + TAIL_WINDOW]
        m_tail = re.match(r"\s*([.,])(\d{1,4})", tail)
        if m_tail:
            sep, frac = m_tail.groups()
            best = f"{best}{sep}{frac}"
        elif re.match(r"\s*[A-Za-z]", tail):
            # Corrupted number like "$12x34" → bail out
            return None

    return best


def _normalize_numeric_string(s: str) -> str | None:
    """
    Keep only digits and separators, resolve thousands/decimal conventions.
    """
    cleaned = re.sub(r"[^\d.,]", "", s)
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        # Assume commas are thousands separators if both present.
        cleaned = cleaned.replace(",", "")
    else:
        # Otherwise, comma acts as decimal separator.
        cleaned = cleaned.replace(",", ".")
    return cleaned


def guess_price(text: str) -> float | None:
    """
    Extract the first detected price-like pattern from the input text.
    """
    match = _search_price_match(text)
    if not match:
        return None

    best = _best_candidate_from_match(match, text)
    if not best:
        return None

    normalized = _normalize_numeric_string(best)
    if not normalized:
        return None

    try:
        return float(normalized)
    except ValueError:
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


def _strip_trailing_price_lines(s: str) -> str:
    """
    Remove any trailing lines that look like a price (e.g., "Price: $12.5" or "19,99 €").
    """
    lines = s.splitlines()
    while lines and re.search(REGEX_PRICE_PATTERN, lines[-1]):
        lines.pop()
    return "\n".join(lines).strip()


def guess_description(text: str) -> str | None:
    """
    Extract a paragraph of medium length from the text as a description.
    """
    paragraphs = re.split(REGEX_PARAGRAPH_SPLIT_PATTERN, text)
    for p in paragraphs:
        candidate = _strip_trailing_price_lines(p.strip())
        if DESCRIPTION_MIN_LENGTH <= len(candidate) <= DESCRIPTION_MAX_LENGTH:
            return candidate
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

    Returns:
        ScrapedItem | None: Structured result if valid, otherwise None.
    """
    logger.debug(MSG_DEBUG_RULE_BASED_START.format(url=request.url))

    title = guess_title(request.text)
    description = guess_description(request.text)
    price = guess_price(request.text)

    logger.debug(MSG_DEBUG_RULE_BASED_TITLE.format(title=title))
    logger.debug(MSG_DEBUG_RULE_BASED_DESCRIPTION.format(description=description))
    logger.debug(MSG_DEBUG_RULE_BASED_PRICE.format(price=price))

    # Rule-based agent - only “informativeness” guard:
    # If we found nothing useful, skip constructing a ScrapedItem and return None.
    if title is None and description is None and price is None:
        logger.warning(MSG_WARN_RULE_BASED_NO_FIELDS.format(url=request.url))
        return None

    screenshot_path: str | None = None
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

    logger.debug(MSG_DEBUG_RULE_BASED_VALIDATION_SUCCESS)
    return item
