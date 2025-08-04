import json
import logging
from typing import Any

from agentic_scraper.backend.config.constants import IMPORTANT_FIELDS, MAX_TEXT_FOR_FEWSHOT
from agentic_scraper.backend.config.messages import MSG_DEBUG_CONTEXTUAL_HINTS_USED
from agentic_scraper.backend.scraper.agent.field_utils import FIELD_WEIGHTS

logger = logging.getLogger(__name__)

FEW_SHOT_EXAMPLE = """
Example:

Page Type: product
Extracted JSON:
{
  "url": "https://example.com/product123",
  "page_type": "product",
  "title": "Logitech MX Master 3",
  "price": "$99.99",
  "description": "Wireless mouse with ergonomic design."
}
"""

SCHEMA_BLOCK = """
Required JSON schema (example fields):
- url (str)
- page_type (str)
- title (str)
- price (str)
- summary (str)
- author (str)
- company (str)
- location (str)
- date (str)
...
"""


def _truncate_fields(fields: dict[str, Any], limit: int = 500) -> str:
    raw = json.dumps(fields, indent=2)
    return raw if len(raw) <= limit else raw[:limit] + "\n... (truncated)"


def _sort_fields_by_weight(fields: set[str]) -> list[str]:
    return sorted(fields, key=lambda f: FIELD_WEIGHTS.get(f, 0), reverse=True)


def build_prompt(
    text: str,
    url: str,
    prompt_style: str = "simple",
    context_hints: dict[str, str] | None = None,
) -> str:
    """
    Unified prompt builder with consistent structure across 'simple' and 'enhanced' styles.

    Args:
        text (str): Cleaned input text content.
        url (str): Page URL.
        prompt_style (str): Either 'simple' or 'enhanced'.
        context_hints (dict[str, str] | None): Optional metadata, breadcrumbs, etc.

    Returns:
        str: Fully constructed prompt string.
    """
    base_message = f"""
You are a smart web content extraction agent.
Your goal is to extract all useful information from the web page below,
based on the type of the web page (product, blog, job) and its context.
Decide which fields to extract accordingly.
Extract as much relevant information as possible.

Instructions:
- Infer the page_type (e.g. product, blog, job).
- Choose fields based on type.
- Only extract values present in the page.
- The following fields are especially important and should be prioritized if found:
{", ".join(IMPORTANT_FIELDS)}, but don't hesitate to add more relevant fields.
- Return only valid JSON.

Mandatory fields: url, page_type.
{SCHEMA_BLOCK}
""".strip()

    if prompt_style == "enhanced":
        page_type = context_hints.get("page") if context_hints else None
        meta = context_hints.get("meta") if context_hints else None
        breadcrumbs = context_hints.get("breadcrumbs") if context_hints else None
        url_segments = context_hints.get("url_segments") if context_hints else None

        logger.debug(
            MSG_DEBUG_CONTEXTUAL_HINTS_USED.format(
                url=url,
                meta=meta or "N/A",
                breadcrumbs=breadcrumbs or "N/A",
                url_segments=url_segments or "N/A",
            )
        )

        context_block = f"""
Extra context:
- Page Type: {page_type or "N/A"}
- Meta tags: {meta or "N/A"}
- Breadcrumbs: {breadcrumbs or "N/A"}
- URL segments: {url_segments or "N/A"}
"""

        example_block = FEW_SHOT_EXAMPLE if len(text) < MAX_TEXT_FOR_FEWSHOT else ""
    else:
        context_block = ""
        example_block = ""

    return f"""
{base_message}

{example_block}
{context_block}

Page URL: {url}

Page Content:
{text[:4000]}
""".strip()


def build_retry_prompt(
    best_fields: dict[str, Any],
    missing_fields: set[str],
) -> str:
    """
    Build a retry prompt that recovers missing required
    fields and expands with other relevant metadata.

    Args:
        best_fields (dict[str, Any]): Previously extracted data (may be partial).
        missing_fields (set[str]): Required fields that were missing in the last attempt.

    Returns:
        str: Retry instruction combining prior output and extraction goals.
    """
    return f"""We previously extracted the following fields:
{_truncate_fields(best_fields)}

However, the following important fields were missing:
{", ".join(_sort_fields_by_weight(missing_fields)) or "None"}.

Instructions:
- Re-analyze the page carefully.
- Fill in the missing required fields listed above.
- Include any additional relevant or useful fields not already present.
- Use your judgment based on the page type and context.
- Extract as much relevant information as possible.

Return only a valid JSON object. Do not include explanations or extra text.
"""


def build_retry_or_fallback_prompt(
    best_fields: dict[str, Any] | None,
    missing_fields: set[str],
) -> str:
    """
    Builds either a focused retry prompt or a general fallback prompt depending on missing fields.

    Args:
        best_fields (dict[str, Any] | None): Previously extracted field values.
        missing_fields (set[str]): Fields the LLM failed to extract.

    Returns:
        str: Retry or fallback prompt for another LLM attempt.
    """
    if missing_fields:
        return build_retry_prompt(best_fields or {}, missing_fields)

    if best_fields:
        return f"""We previously extracted the following fields:
{_truncate_fields(best_fields)}

Instructions:
- Analyze the content again and extract any additional useful or contextually important fields.
- If possible, improve or extend previously extracted fields (do not just repeat them).
- Use your judgment based on the page type and context.

Return only a valid JSON object. Do not include explanations or extra text.
"""

    return (
        "Analyze the content and extract all useful, relevant, or structured fields. "
        "Use your best judgment to infer fields based on page context and type. "
        "Return only a valid JSON object. Do not include explanations or extra text."
    )
