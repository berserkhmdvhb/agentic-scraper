"""
Rule-based scraping agent for extracting structured data using regex heuristics.

Responsibilities:
- Infer common fields (title, description, price) from plain text.
- Use defensive, locale-tolerant regexes for currency/number patterns.
- Optionally capture a screenshot via Playwright (delegated helper).
- Validate and return a `ScrapedItem`, or `None` when nothing useful is found.

Public API:
- `extract_structured_data`: Main entry point; returns a validated `ScrapedItem | None`.
- `guess_title`: First non-empty line heuristic.
- `guess_description`: Medium-length paragraph heuristic (price tails removed).
- `guess_price`: Regex-based price detection with fallbacks.

Operational:
- Concurrency: Pure async; designed to be called by worker tasks.
- Logging: Uses message constants; verbose logs include field previews.
- Dependencies: Screenshotting is performed via helper if `take_screenshot=True`.

Usage:
    from agentic_scraper.backend.scraper.agent.rule_based import extract_structured_data

    item = await extract_structured_data(request, settings=settings)
    if item is not None:
        print(item.model_dump())

Notes:
- Heuristics are intentionally conservative to avoid false positives.
- Price parsing tolerates common thousands/decimal separators (',' vs '.').
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

# ──────────────────────────────────────────────────────────────────────────────
# Price-detection helpers & regexes
# ──────────────────────────────────────────────────────────────────────────────
# Heuristic knobs tuned by observation:
MIN_GROUPS_FOR_DECIMAL = 2  # e.g., groups like ("12", "99") → "12.99"
TAIL_WINDOW = 6  # how far to peek after a number for a fractional tail

# Fallbacks for "$ 12.34" vs "12.34 $" when the primary project pattern misses.
# Keep permissive groupings to accommodate "12,345.67" and "12.345,67".
_FALLBACK_NUM_THEN_CURR = re.compile(r"(\d{1,3}(?:[.,]\d{3})*[.,]?\d{1,4})\s*[€$]")
_FALLBACK_CURR_THEN_NUM = re.compile(r"[€$]\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]?\d{1,4})?)")


def _search_price_match(text: str) -> re.Match[str] | None:
    """
    Try the main project price pattern, then currency/number fallbacks.

    Returns:
        re.Match | None: First match if any; otherwise None.

    Notes:
        - Ordering matters: prefer project pattern to keep behavior stable.
    """
    m = re.search(REGEX_PRICE_PATTERN, text)
    if m:
        return m
    return _FALLBACK_NUM_THEN_CURR.search(text) or _FALLBACK_CURR_THEN_NUM.search(text)


def _best_candidate_from_match(m: re.Match[str], text: str) -> str | None:
    """
    Choose the most price-like candidate from a regex match (group or whole).

    Heuristics:
    - Prefer tokens with separators and more digits.
    - If groups resemble integer + fraction without a separator, synthesize one.
    - If still no separator, peek a short tail to capture a fractional part.

    Args:
        m (re.Match): A match that likely contains a price.
        text (str): Full text to allow post-match tail inspection.

    Returns:
        str | None: Best candidate string, or None if corrupted (e.g., "$12x34").
    """
    groups = [g for g in (m.groups() or ()) if g]
    candidates = [*groups, m.group(0)]

    def _score(s: str) -> tuple[int, int, int]:
        has_sep = 1 if ("," in s or "." in s) else 0
        digit_count = sum(ch.isdigit() for ch in s)
        return (has_sep, digit_count, len(s))

    best = max(candidates, key=_score)

    # Synthesize decimal if groups look like integer + fractional without a separator
    # e.g., ("12", "99") → "12.99".
    if len(groups) >= MIN_GROUPS_FOR_DECIMAL and ("." not in best and "," not in best):
        combined = f"{groups[0]}.{groups[1]}"
        best = max([*candidates, combined], key=_score)

    # If no separator yet, peek right after the match for a short fractional tail.
    if "." not in best and "," not in best:
        tail = text[m.end() : m.end() + TAIL_WINDOW]
        m_tail = re.match(r"\s*([.,])(\d{1,4})", tail)
        if m_tail:
            sep, frac = m_tail.groups()
            best = f"{best}{sep}{frac}"
        elif re.match(r"\s*[A-Za-z]", tail):
            # Corrupted number like "$12x34" → bail out.
            return None

    return best


def _normalize_numeric_string(s: str) -> str | None:
    """
    Keep only digits and separators, then normalize separators.

    Rules:
    - If both ',' and '.' exist → assume ',' are thousands separators, strip them.
    - Else: treat ',' as decimal separator and convert to '.'.

    Returns:
        str | None: Normalized numeric string or None if empty.
    """
    cleaned = re.sub(r"[^\d.,]", "", s)
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")  # favor '.' as decimal sep when both present
    else:
        cleaned = cleaned.replace(",", ".")  # single ',' → decimal sep
    return cleaned


def guess_price(text: str) -> float | None:
    """
    Extract the first detected price-like value from text.

    Args:
        text (str): Full page text.

    Returns:
        float | None: Parsed price in decimal form, or None if no reliable hit.

    Examples:
        >>> guess_price("Only $12.50 today!")
        12.5
        >>> guess_price("Preis: 1.234,99 €")
        1234.99
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
        # Defensive: if normalization still yields a non-float string, drop it.
        return None


def guess_title(text: str) -> str | None:
    """
    Use the first non-empty line as a title candidate.

    Args:
        text (str): Full page text.

    Returns:
        str | None: Title candidate or None.

    Examples:
        >>> guess_title("Hello\\nWorld")
        'Hello'
    """
    for line in text.strip().splitlines():
        clean = line.strip()
        if clean:
            return clean
    return None


def _strip_trailing_price_lines(s: str) -> str:
    """
    Remove trailing lines that look like prices (e.g., "19,99 €" at the end).

    Rationale:
        Product pages often terminate paragraphs with a price; this muddies
        description quality for downstream LLMs, so we trim those tails.
    """
    lines = s.splitlines()
    while lines and re.search(REGEX_PRICE_PATTERN, lines[-1]):
        lines.pop()
    return "\n".join(lines).strip()


def guess_description(text: str) -> str | None:
    """
    Extract a medium-length paragraph as description.

    Strategy:
        Split by paragraph boundaries, trim price-like tails, and select the first
        candidate whose length is within [DESCRIPTION_MIN_LENGTH, DESCRIPTION_MAX_LENGTH].

    Args:
        text (str): Full page text.

    Returns:
        str | None: Description paragraph or None if no suitable candidate.
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
    Perform rule-based extraction and return a validated `ScrapedItem`.

    Args:
        request (ScrapeRequest): Prepared request (url, text, flags, creds).
        settings (Settings): Global runtime settings (logging, screenshot flag, etc.).

    Returns:
        ScrapedItem | None: Structured item or None when no informative fields are found.

    Notes:
        - Screenshot capture is delegated and optional; failures are logged by the helper.
        - Validation errors are logged with field previews in debug logs.
    """
    logger.debug(MSG_DEBUG_RULE_BASED_START.format(url=request.url))

    # Field inference via simple text/regex heuristics.
    title = guess_title(request.text)
    description = guess_description(request.text)
    price = guess_price(request.text)

    logger.debug(MSG_DEBUG_RULE_BASED_TITLE.format(title=title))
    logger.debug(MSG_DEBUG_RULE_BASED_DESCRIPTION.format(description=description))
    logger.debug(MSG_DEBUG_RULE_BASED_PRICE.format(price=price))

    # Informativeness guard: if *nothing* useful was found, prefer returning None
    # over emitting an empty/low-signal item.
    if title is None and description is None and price is None:
        logger.warning(MSG_WARN_RULE_BASED_NO_FIELDS.format(url=request.url))
        return None

    # Optional screenshot (best-effort).
    screenshot_path: str | None = None
    if request.take_screenshot:
        screenshot_path = await capture_optional_screenshot(request.url, settings)

    # Structured log for quick inspection in verbose mode.
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

    # Validate against internal schema; reject if coercion fails.
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
