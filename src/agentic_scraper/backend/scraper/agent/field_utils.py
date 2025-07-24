from typing import Any

from agentic_scraper.backend.config.constants import FIELD_SYNONYMS

PAGE_TYPE_TO_FIELDS: dict[str, set[str]] = {
    "product": {"title", "price", "description"},
    "job": {"job_title", "company", "location", "date_posted"},
    "blog": {"title", "author", "date", "summary"},
}

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
    Normalize keys by mapping known synonyms (e.g. 'cost' → 'price')
    to their canonical field names.
    """
    return {FIELD_SYNONYMS.get(k, k): v for k, v in raw.items()}


def score_fields(fields: set[str]) -> int:
    """
    Compute a weighted score based on the presence of high-value fields.
    Used to compare extraction quality across retries.
    """
    return sum(FIELD_WEIGHTS.get(f, 0) for f in fields)


def get_required_fields(page_type: str) -> set[str]:
    """
    Return the set of required fields expected for the given page_type.
    Falls back to an empty set if unknown.
    """
    return PAGE_TYPE_TO_FIELDS.get(page_type.lower().strip(), set())
