"""
Field normalization and scoring utilities for LLM-extracted data.

Responsibilities:
- Normalize raw field keys (synonyms → canonical schema names).
- Normalize raw field values (strip placeholders, coerce types).
- Provide field importance weights for scoring extraction quality.
- Detect placeholders like "N/A" to skip redundant retries.
- Map page types to their required canonical fields.

Public API:
- `normalize_keys`: Map synonym keys to canonical schema keys.
- `normalize_value`: Normalize a single value by type and placeholder rules.
- `normalize_fields`: Normalize an entire dict of field values.
- `score_nonempty_fields`: Compute weighted score for extraction quality.
- `get_required_fields`: Return required fields for a given page type.
- `detect_unavailable_fields`: Detect which fields are syntactic placeholders.

Usage:
    from agentic_scraper.backend.scraper.agents.field_utils import normalize_fields

    fields = {"cost": "99.99", "desc": "A great product", "author": "Dana"}
    normalized = normalize_fields(fields)
    # -> {"price": 99.99, "description": "A great product", "author": "Dana"}

Notes:
- Logs debug messages when keys are normalized or placeholders are detected.
- Unknown keys/values are passed through unchanged.
"""

import logging
from typing import Any

from agentic_scraper.backend.config.constants import FIELD_SYNONYMS
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_NORMALIZED_KEYS,
    MSG_DEBUG_UNAVAILABLE_FIELDS_DETECTED,
)

logger = logging.getLogger(__name__)

__all__ = [
    "FIELD_WEIGHTS",
    "PAGE_TYPE_TO_FIELDS",
    "detect_unavailable_fields",
    "get_required_fields",
    "normalize_fields",
    "normalize_keys",
    "normalize_value",
    "score_nonempty_fields",
]

# Strings commonly used on websites to mean "no value available"
PLACEHOLDER_VALUES = {"not specified", "n/a", "none", "unknown", "-", ""}

# Mapping of page types to the canonical fields expected for extraction.
PAGE_TYPE_TO_FIELDS: dict[str, set[str]] = {
    "product": {"title", "price", "description"},
    "job": {"job_title", "company", "location", "date_posted"},
    "blog": {"title", "author", "date", "summary"},
}

# Importance weight of each field for scoring extraction quality.
FIELD_WEIGHTS: dict[str, int] = {
    "title": 3,
    "price": 3,
    "summary": 2,
    "description": 2,
    "author": 2,
    "company": 2,
    "location": 1,
    "date": 1,
    "date_posted": 1,
    "job_title": 2,
}


def normalize_keys(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize field names in a dictionary using FIELD_SYNONYMS.

    For example, 'cost' or 'amount' may be remapped to 'price'.

    Args:
        raw (dict[str, Any]): Dictionary of extracted fields.

    Returns:
        dict[str, Any]: Dictionary with normalized field names.
    """
    original_keys = list(raw.keys())
    normalized = {FIELD_SYNONYMS.get(k, k): v for k, v in raw.items()}
    logger.debug(
        MSG_DEBUG_NORMALIZED_KEYS.format(original=original_keys, normalized=list(normalized.keys()))
    )
    return normalized


def score_nonempty_fields(data: dict[str, Any]) -> float:
    """
    Compute a hybrid score for extracted fields based on importance and coverage.

    Args:
        data (dict[str, Any]): Dictionary of extracted fields with values.

    Returns:
        float: Weighted score combining important known fields and bonus for general coverage.

    Notes:
        - Unknown fields contribute a base weight of 0.3.
        - Empty values (None or empty string) are ignored.
    """
    base_score = 0.3
    score = 0.0
    for key, value in data.items():
        if value in [None, ""]:
            continue
        score += FIELD_WEIGHTS.get(key, base_score)
    return score


def get_required_fields(page_type: str | list[str] | None) -> set[str]:
    """
    Get the expected required fields for a given page type.

    Args:
        page_type (str | list[str] | None): Page type name or list (first element used).
            If unrecognized, returns an empty set.

    Returns:
        set[str]: Canonical required field names.
    """
    if isinstance(page_type, list):
        page_type = page_type[0] if page_type else ""
    elif not isinstance(page_type, str):
        page_type = ""
    return PAGE_TYPE_TO_FIELDS.get(page_type.lower().strip(), set())


def normalize_value(
    value: str | float | None,
    target_type: type[float] | type[int] | type[str],
) -> float | int | str | None:
    """
    Normalize a raw value based on its expected target type.

    This function coerces the input into the specified type (float, int, or str),
    while treating placeholder values (e.g., "n/a", "not specified") as None.

    Args:
        value (str | float | None): The raw value to normalize.
        target_type (type): The target type (float, int, or str).

    Returns:
        float | int | str | None: Normalized value if valid, else None.

    Notes:
        - Placeholder values (see PLACEHOLDER_VALUES) are mapped to None.
        - Strings are stripped of whitespace before normalization.
        - Returns None if coercion fails (ValueError or TypeError).
    """
    if value is None:
        return None

    if isinstance(value, str) and value.strip().lower() in PLACEHOLDER_VALUES:
        return None

    result: float | int | str | None = None
    try:
        if target_type is float:
            result = float(value)
        elif target_type is int:
            result = int(value)
        elif target_type is str:
            result = str(value).strip()
    except (ValueError, TypeError):
        result = None

    return result


def normalize_fields(raw_fields: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize an entire dict of extracted fields to expected schema formats.

    Args:
        raw_fields (dict[str, Any]): Dictionary of raw field values.

    Returns:
        dict[str, Any]: Dictionary with normalized values for known keys.

    Notes:
        - Price coerced to float.
        - Strings stripped and placeholders removed.
        - Unknown keys/values passed through unchanged.
    """
    normalized = {}
    for key, value in raw_fields.items():
        if key == "price":
            normalized[key] = normalize_value(value, float)
        elif key == "date_published":
            normalized[key] = str(value).strip() if value else None
        elif key in {
            "title",
            "description",
            "author",
            "summary",
            "job_title",
            "company",
            "location",
            "job_type",
            "application_deadline",
        }:
            normalized[key] = normalize_value(value, str)
        elif key == "url":
            normalized[key] = str(value).strip() if value else None
        else:
            normalized[key] = value  # Unknown/unhandled: pass through
    return normalized


def detect_unavailable_fields(raw: dict[str, Any]) -> set[str]:
    """
    Detect which fields contain syntactic placeholders like "n/a" or "unknown".

    Args:
        raw (dict[str, Any]): Dictionary of raw extracted values.

    Returns:
        set[str]: Field names flagged as placeholders.

    Notes:
        - Logged at debug level with sorted field names.
        - Used by adaptive retry logic to avoid retrying known-unavailable fields.
    """
    unavailable = set()
    for k, v in raw.items():
        if isinstance(v, str) and v.strip().lower() in PLACEHOLDER_VALUES:
            unavailable.add(k)
    if unavailable:
        logger.debug(MSG_DEBUG_UNAVAILABLE_FIELDS_DETECTED.format(fields=sorted(unavailable)))
    return unavailable
