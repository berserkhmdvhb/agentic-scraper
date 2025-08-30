from __future__ import annotations

import re
from typing import TYPE_CHECKING

from agentic_scraper.backend.config.constants import MAX_TEXT_FOR_FEWSHOT
from agentic_scraper.backend.scraper.agents.field_utils import FIELD_WEIGHTS
from agentic_scraper.backend.scraper.agents.prompt_helpers import (
    _sort_fields_by_weight,
    _truncate_fields,
    build_prompt,
    build_retry_or_fallback_prompt,
    build_retry_prompt,
)

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture


# Test constants (avoid “magic numbers” in assertions)
PROMPT_CONTENT_SLICE = 4000  # mirrors build_prompt's slice
SHORT_TEXT_LEN = max(10, MAX_TEXT_FOR_FEWSHOT - 5)
LONG_TEXT_LEN = MAX_TEXT_FOR_FEWSHOT + 100


# ------------------------------ _truncate_fields ------------------------------ #


def test_truncate_fields_truncates_when_over_limit() -> None:
    payload = {"a": "x" * 1000}
    limited = _truncate_fields(payload, limit=50)
    assert limited.endswith("... (truncated)")
    # Keep a quick sanity check that JSON began correctly
    assert limited.startswith(("{", "{\n"))


def test_truncate_fields_no_truncation_under_limit() -> None:
    payload = {"a": "b"}
    out = _truncate_fields(payload, limit=500)
    assert "... (truncated)" not in out
    assert '"a": "b"' in out


# ------------------------------ _sort_fields_by_weight ------------------------------ #


def test_sort_fields_by_weight_descending_and_unknowns_last() -> None:
    fields = {"title", "summary", "price", "totally_unknown"}
    sorted_fields = _sort_fields_by_weight(fields)
    # Expected: price (3) and title (3) first (any order between them),
    # then summary (2), then unknown (0)
    idx = {name: sorted_fields.index(name) for name in fields}
    assert idx["summary"] > idx["title"] or idx["summary"] > idx["price"]
    assert idx["totally_unknown"] == len(sorted_fields) - 1
    # Sanity: weights respected globally
    assert (
        FIELD_WEIGHTS["summary"] < FIELD_WEIGHTS["title"]
        or FIELD_WEIGHTS["summary"] < FIELD_WEIGHTS["price"]
    )


# ------------------------------ build_prompt ------------------------------ #


def _extract_page_content_block(prompt: str) -> str:
    """Return the substring following 'Page Content:' including the content."""
    m = re.search(r"Page Content:\n(.+)\Z", prompt, flags=re.DOTALL)
    return m.group(1) if m else ""


def test_build_prompt_simple_truncates_page_content() -> None:
    text = "A" * (PROMPT_CONTENT_SLICE + 500)
    prompt = build_prompt(
        text=text, url="https://example.org", prompt_style="simple", context_hints=None
    )
    content = _extract_page_content_block(prompt)
    assert content.startswith("A" * PROMPT_CONTENT_SLICE)
    assert "A" * (PROMPT_CONTENT_SLICE + 1) not in content  # ensure sliced
    assert "Page URL: https://example.org" in prompt


def test_build_prompt_enhanced_includes_context_and_example_when_short(
    caplog: LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG")
    short_text = "B" * SHORT_TEXT_LEN
    ctx = {
        "page": "product",
        "meta": "title=Thing; description=Nice",
        "breadcrumbs": "Home > Thing",
        "url_segments": "products / thing",
    }
    prompt = build_prompt(
        text=short_text,
        url="https://example.org/p/thing",
        prompt_style="enhanced",
        context_hints=ctx,
    )
    # Context block present
    assert "Extra context:" in prompt
    assert "Page Type: product" in prompt
    assert "Meta tags: title=Thing; description=Nice" in prompt
    assert "Breadcrumbs: Home > Thing" in prompt
    assert "URL segments: products / thing" in prompt
    # Few-shot example included because text is short
    assert "Example:" in prompt


def test_build_prompt_enhanced_omits_example_when_long() -> None:
    long_text = "C" * LONG_TEXT_LEN
    prompt = build_prompt(
        text=long_text,
        url="https://example.org/big",
        prompt_style="enhanced",
        context_hints={"page": "blog"},
    )
    assert "Extra context:" in prompt
    assert "Example:" not in prompt


# ------------------------------ build_retry_prompt ------------------------------ #


def test_build_retry_prompt_orders_missing_fields_by_weight() -> None:
    best = {"url": "https://x", "title": "T"}
    missing = {"summary", "price", "location"}  # weights: 2, 3, 1
    text = build_retry_prompt(best_fields=best, missing_fields=missing)
    # price should appear before summary which should appear before location
    price_idx = text.find("price")
    summary_idx = text.find("summary")
    location_idx = text.find("location")
    assert 0 <= price_idx < summary_idx < location_idx


# ------------------------------ build_retry_or_fallback_prompt ------------------------------ #


def test_build_retry_or_fallback_prompt_takes_retry_path_when_missing_present() -> None:
    best = {"url": "https://x", "title": "T"}
    missing = {"author"}
    out = build_retry_or_fallback_prompt(best_fields=best, missing_fields=missing)
    assert "We previously extracted the following fields" in out
    assert "author" in out


def test_build_retry_or_fallback_prompt_takes_fallback_when_no_missing_but_best_exists() -> None:
    best = {"url": "https://x", "title": "T", "summary": "S"}
    out = build_retry_or_fallback_prompt(best_fields=best, missing_fields=set())
    assert "We previously extracted the following fields" in out
    assert '"title"' in out or "title" in out  # serialized JSON presence


def test_build_retry_or_fallback_prompt_generic_when_no_best_and_no_missing() -> None:
    out = build_retry_or_fallback_prompt(best_fields=None, missing_fields=set())
    assert "Analyze the content and extract all useful" in out
