from typing import Any

from agentic_scraper.backend.config.constants import FIELD_SYNONYMS

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
