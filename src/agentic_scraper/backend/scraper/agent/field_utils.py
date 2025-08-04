from typing import Any

from agentic_scraper.backend.config.constants import FIELD_SYNONYMS

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
    This helps align LLM outputs with expected schema.

    Args:
        raw (dict[str, Any]): Dictionary of extracted fields.

    Returns:
        dict[str, Any]: Dictionary with normalized field names.
    """
    return {FIELD_SYNONYMS.get(k, k): v for k, v in raw.items()}


def score_nonempty_fields(data: dict[str, Any]) -> float:
    """
    Compute a hybrid score for extracted fields based on importance and coverage.

    Args:
        data (dict[str, Any]): Dictionary of extracted fields with values.

    Returns:
        float: Weighted score combining important known fields and bonus for general coverage.
    """
    base_score = 0.3  # For unknown fields
    score = 0.0

    for key, value in data.items():
        if value in [None, ""]:
            continue
        score += FIELD_WEIGHTS.get(key, base_score)

    return score


def get_required_fields(page_type: str | list[str] | None) -> set[str]:
    """
    Get the expected fields for a given page type.

    Args:
        page_type (str | list[str] | None): The page type, optionally a list.
            If a list is given, the first entry is used.
            If None or unrecognized, returns an empty set.

    Returns:
        set[str]: Set of required canonical field names.
    """
    if isinstance(page_type, list):
        page_type = page_type[0] if page_type else ""
    elif not isinstance(page_type, str):
        page_type = ""
    return PAGE_TYPE_TO_FIELDS.get(page_type.lower().strip(), set())


# ─────────────────────────────────────────────────────────────────────────────
# Normalizers
# ─────────────────────────────────────────────────────────────────────────────


def normalize_value(
    value: str | float | None,
    target_type: type[float] | type[int] | type[str],
) -> float | int | str | None:
    """Normalize a value based on its expected target type."""
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
    """Normalize raw LLM fields to match schema expectations."""
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
            # Unknown or unhandled fields: pass through untouched
            normalized[key] = value

    return normalized


def detect_unavailable_fields(raw: dict[str, Any]) -> set[str]:
    """Detect fields whose raw values indicate 'not available' semantics."""
    unavailable = set()
    for k, v in raw.items():
        if isinstance(v, str) and v.strip().lower() in PLACEHOLDER_VALUES:
            unavailable.add(k)
    return unavailable
