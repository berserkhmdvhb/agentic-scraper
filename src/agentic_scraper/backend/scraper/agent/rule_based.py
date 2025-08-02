import logging
import re

from pydantic import HttpUrl, ValidationError

from agentic_scraper.backend.config.constants import (
    DESCRIPTION_MAX_LENGTH,
    DESCRIPTION_MIN_LENGTH,
    REGEX_PARAGRAPH_SPLIT_PATTERN,
    REGEX_PRICE_PATTERN,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_RULE_BASED_EXTRACTION_FAILED,
)
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.agent.agent_helpers import (
    capture_optional_screenshot,
    log_structured_data,
)
from agentic_scraper.backend.scraper.models import ScrapedItem, ScrapeRequest

logger = logging.getLogger(__name__)


def guess_price(text: str) -> float | None:
    price_match = re.search(REGEX_PRICE_PATTERN, text)
    if price_match:
        try:
            return float(price_match.group(1).replace(",", "."))
        except ValueError:
            return None
    return None


def guess_title(text: str) -> str | None:
    for line in text.strip().splitlines():
        clean = line.strip()
        if clean:
            return clean
    return None


def guess_description(text: str) -> str | None:
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
    title = guess_title(request.text)
    description = guess_description(request.text)
    price = guess_price(request.text)
    screenshot_path: str | None = None

    logger.debug(f"[RULE_BASED] Attempting extraction for URL: {request.url}")
    logger.debug(f"[RULE_BASED] Title guessed: {title}")
    logger.debug(f"[RULE_BASED] Description guessed: {description}")
    logger.debug(f"[RULE_BASED] Price guessed: {price}")

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
        logger.debug(f"[RULE_BASED] ✅ Validation succeeded. Returning ScrapedItem.")
        return item

    except ValidationError as exc:
        logger.error(MSG_DEBUG_RULE_BASED_EXTRACTION_FAILED.format(url=request.url, error=exc))
        logger.debug(
            "[RULE_BASED] Validation failed for fields: title=%r, description=%r, price=%r, url=%r",
            title, description, price, request.url
        )
        return None
