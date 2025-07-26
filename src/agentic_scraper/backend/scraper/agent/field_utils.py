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


def score_fields(fields: set[str]) -> int:
    """
    Compute a weighted score for a set of fields based on FIELD_WEIGHTS.

    Higher weights are assigned to more important fields (e.g., 'title', 'price').
    This is used to compare and rank different LLM outputs by quality.

    Args:
        fields (set[str]): Set of normalized field names.

    Returns:
        int: Total weighted score.
    """
    return sum(FIELD_WEIGHTS.get(f, 0) for f in fields)


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
