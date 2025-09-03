from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from agentic_scraper.backend.config.constants import FIELD_SYNONYMS
from agentic_scraper.backend.scraper.agents.field_utils import (
    FIELD_WEIGHTS,
    detect_unavailable_fields,
    get_required_fields,
    normalize_fields,
    normalize_keys,
    normalize_value,
    score_nonempty_fields,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


# Test constants to avoid "magic values" in assertions
VAL_UNCHANGED = 123
VAL_FLOAT = 12.5
VAL_INT = 7
VAL_PRICE = 12.5


def _first_synonym_pair() -> Iterator[tuple[str, str]]:
    """Yield the first (alias, canonical) pair from FIELD_SYNONYMS, if any."""
    for alias, canonical in FIELD_SYNONYMS.items():
        yield alias, canonical
        break


# ------------------------------ normalize_keys ------------------------------ #


def test_normalize_keys_uses_field_synonyms() -> None:
    pairs = list(_first_synonym_pair())
    if not pairs:
        pytest.skip("No FIELD_SYNONYMS configured; skipping mapping test.")
    alias, canonical = pairs[0]

    raw = {alias: "value", "unchanged": VAL_UNCHANGED}
    out = normalize_keys(raw)

    assert canonical in out
    assert "unchanged" in out
    assert alias not in out
    assert out[canonical] == "value"
    assert out["unchanged"] == VAL_UNCHANGED


# ------------------------------ score_nonempty_fields ------------------------------ #


def test_score_nonempty_fields_mixed_known_and_unknown() -> None:
    # Known keys: title (3), price (3), summary (2)
    # Unknown key contributes base 0.3 (see implementation).
    data = {
        "title": "T",
        "price": 1.0,
        "summary": "s",
        "description": "",  # ignored
        "author": None,  # ignored
        "totally_unknown": "x",
    }
    expected = FIELD_WEIGHTS["title"] + FIELD_WEIGHTS["price"] + FIELD_WEIGHTS["summary"] + 0.3
    assert score_nonempty_fields(data) == pytest.approx(expected)


# ------------------------------ get_required_fields ------------------------------ #


def test_get_required_fields_for_job_and_list_variants() -> None:
    expected = {"job_title", "company", "location", "date_posted"}
    assert get_required_fields("job") == expected
    # Accepts list input; uses first element, case-insensitive, trims
    assert get_required_fields(["  JOB  "]) == expected
    # Unknown page type => empty set
    assert get_required_fields("unknown-type") == set()


# ------------------------------ normalize_value ------------------------------ #


def test_normalize_value_coercions_and_placeholders() -> None:
    assert normalize_value(str(VAL_FLOAT), float) == VAL_FLOAT
    assert normalize_value(str(VAL_INT), int) == VAL_INT
    assert normalize_value(3.0, str) == "3.0"

    # Placeholders -> None
    assert normalize_value("  n/a ", str) is None
    assert normalize_value("-", str) is None
    assert normalize_value(None, str) is None


# ------------------------------ normalize_fields ------------------------------ #


def test_normalize_fields_end_to_end() -> None:
    raw = {
        "price": str(VAL_PRICE),
        "date_published": " 2024-05-01 ",
        "title": "  Hello  ",
        "author": "  Jane ",
        "url": " https://example.org/page ",
        "unknown": "keep-me",
    }
    out = normalize_fields(raw)

    assert out["price"] == VAL_PRICE
    assert out["date_published"] == "2024-05-01"
    assert out["title"] == "Hello"
    assert out["author"] == "Jane"
    assert out["url"] == "https://example.org/page"
    assert out["unknown"] == "keep-me"


# ------------------------------ detect_unavailable_fields ------------------------------ #


def test_detect_unavailable_fields_flags_placeholders() -> None:
    raw = {
        "title": "N/A",
        "description": "not specified",
        "price": "",
        "author": "unknown",
        "real": "ok",
    }
    unavailable = detect_unavailable_fields(raw)

    # These should definitely be flagged as placeholders
    for k in ("title", "description", "price", "author"):
        assert k in unavailable
    # Real value should not be flagged
    assert "real" not in unavailable
