import logging
import re
from pathlib import Path

from playwright.async_api import Error as PlaywrightError
from pydantic import HttpUrl, ValidationError

from agentic_scraper.backend.config.constants import (
    DESCRIPTION_MAX_LENGTH,
    DESCRIPTION_MIN_LENGTH,
    REGEX_PARAGRAPH_SPLIT_PATTERN,
    REGEX_PRICE_PATTERN,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_PARSED_STRUCTURED_DATA,
    MSG_DEBUG_RULE_BASED_EXTRACTION_FAILED,
    MSG_ERROR_SCREENSHOT_FAILED_WITH_URL,
)
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.backend.scraper.screenshotter import capture_screenshot

logger = logging.getLogger(__name__)


def guess_price(text: str) -> float | None:
    """Find and return the first valid-looking price in the text."""
    price_match = re.search(REGEX_PRICE_PATTERN, text)
    if price_match:
        try:
            return float(price_match.group(1).replace(",", "."))
        except ValueError:
            return None
    return None


def guess_title(text: str) -> str | None:
    """Return the first non-empty line as a title."""
    for line in text.strip().splitlines():
        clean = line.strip()
        if clean:
            return clean
    return None


def guess_description(text: str) -> str | None:
    """Return the first paragraph with a reasonable length."""
    paragraphs = re.split(REGEX_PARAGRAPH_SPLIT_PATTERN, text)
    for p in paragraphs:
        clean = p.strip()
        if DESCRIPTION_MIN_LENGTH <= len(clean) <= DESCRIPTION_MAX_LENGTH:
            return clean
    return None


async def extract_structured_data(
    text: str,
    url: str,
    *,
    take_screenshot: bool = False,
    settings: Settings,
) -> ScrapedItem | None:
    """
    Rule-based fallback extraction from plain text input.
    """
    title = guess_title(text)
    description = guess_description(text)
    price = guess_price(text)
    screenshot_path: str | None = None

    if take_screenshot:
        try:
            screenshot_path = await capture_screenshot(
                url, output_dir=Path(settings.screenshot_dir)
            )
        except (PlaywrightError, OSError, ValueError):
            logger.warning(MSG_ERROR_SCREENSHOT_FAILED_WITH_URL, url)

    if settings.is_verbose_mode:
        logger.debug(
            MSG_DEBUG_PARSED_STRUCTURED_DATA,
            {
                "title": title,
                "description": description,
                "price": price,
                "author": None,
                "date_published": None,
                "screenshot_path": screenshot_path,
            },
        )

    try:
        return ScrapedItem(
            url=HttpUrl(url),
            title=title,
            description=description,
            price=price,
            author=None,
            date_published=None,
            screenshot_path=screenshot_path,
        )
    except ValidationError as e:
        logger.warning(MSG_DEBUG_RULE_BASED_EXTRACTION_FAILED.format(url=url, error=e))
        return None
