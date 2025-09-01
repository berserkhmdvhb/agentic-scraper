from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from agentic_scraper.backend.config.constants import (
    DESCRIPTION_MAX_LENGTH,
    DESCRIPTION_MIN_LENGTH,
)
from agentic_scraper.backend.scraper.agents import rule_based as rb
from agentic_scraper.backend.scraper.models import ScrapeRequest
from agentic_scraper.backend.scraper.schemas import ScrapedItem

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture

    from agentic_scraper.backend.core.settings import Settings

# ------------------------- constants for tests (no magic) ------------------------- #

PRICE_SIMPLE = 12.5
PRICE_EURO = 19.99
SHORT_DESC = "x" * (DESCRIPTION_MIN_LENGTH - 1)
GOOD_DESC = "x" * ((DESCRIPTION_MIN_LENGTH + DESCRIPTION_MAX_LENGTH) // 2)
LONG_DESC = "x" * (DESCRIPTION_MAX_LENGTH + 5)

# -------------------------------- unit tests for helpers ------------------------- #


def test_guess_price_simple() -> None:
    text = f"Title\nPrice: ${PRICE_SIMPLE}\n"
    out = rb.guess_price(text)
    assert out == PRICE_SIMPLE


def test_guess_price_comma_decimal() -> None:
    text = f"Only EUR: {str(PRICE_EURO).replace('.', ',')} €"
    out = rb.guess_price(text)
    # Our guess_price replaces comma with dot, so it should parse to a float equal to 19.99
    assert out == PRICE_EURO


def test_guess_price_invalid_match_returns_none() -> None:
    # Force a "price-like" match that can't parse as float (e.g., captured group contains letters)
    # Using the same regex, but inject a string that still contains letters after replacement.
    text = "Price: $12x34"
    out = rb.guess_price(text)
    assert out is None


def test_guess_title_picks_first_nonempty_line() -> None:
    text = "\n\n  \t \nMy Product Title\nAnother line\n"
    out = rb.guess_title(text)
    assert out == "My Product Title"


def test_guess_description_picks_medium_paragraph() -> None:
    text = f"{SHORT_DESC}\n\n{GOOD_DESC}\n\n{LONG_DESC}"
    out = rb.guess_description(text)
    assert out == GOOD_DESC


def test_guess_description_returns_none_when_no_suitable_paragraph() -> None:
    text = f"{SHORT_DESC}\n\n{LONG_DESC}"
    out = rb.guess_description(text)
    assert out is None


# ------------------------------- extract_structured_data -------------------------- #


@pytest.mark.asyncio
async def test_extract_structured_data_success_without_screenshot(
    settings: Settings,
) -> None:
    text = f"My Title\n\n{GOOD_DESC}\nPrice: ${PRICE_SIMPLE}"
    req = ScrapeRequest(url="https://example.com/x", text=text, take_screenshot=False)

    out = await rb.extract_structured_data(req, settings=settings)
    assert isinstance(out, ScrapedItem)
    assert out.url == "https://example.com/x"
    assert out.title == "My Title"
    assert out.description == GOOD_DESC
    assert out.price == PRICE_SIMPLE
    assert out.screenshot_path is None


@pytest.mark.asyncio
async def test_extract_structured_data_calls_screenshot_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    text = f"My Title\n\n{GOOD_DESC}\nPrice: ${PRICE_SIMPLE}"
    req = ScrapeRequest(url="https://example.com/y", text=text, take_screenshot=True)

    calls: list[str] = []

    async def _fake_capture(url: str, settings: Settings) -> str | None:
        _ = settings
        calls.append(url)
        return Path("snap.png").as_posix()

    monkeypatch.setattr(rb, "capture_optional_screenshot", _fake_capture, raising=True)

    out = await rb.extract_structured_data(req, settings=settings)
    assert isinstance(out, ScrapedItem)
    assert calls == ["https://example.com/y"]
    assert out.screenshot_path == Path("snap.png").as_posix()


@pytest.mark.asyncio
async def test_extract_structured_data_minimal_fields_still_returns_item(
    settings: Settings,
    caplog: LogCaptureFixture,
) -> None:
    """
    With the current contract, rule-based extraction should return an item
    if it finds any informative field (e.g., title or price), even if
    description is missing.
    """
    caplog.set_level("WARNING", logger="agentic_scraper.backend.scraper.agents.rule_based")

    text = "X\n\nshort\n\nPrice: $1"  # title present, description too short, price present
    req = ScrapeRequest(url="https://example.com/minimal", text=text, take_screenshot=False)

    out = await rb.extract_structured_data(req, settings=settings)
    assert isinstance(out, ScrapedItem)
    assert out.url == "https://example.com/minimal"
    assert out.title == "X"
    assert out.description is None
    assert out.price == 1.0

    # Ensure we did NOT log the "no fields" warning
    assert "produced no informative fields" not in caplog.text.lower()
