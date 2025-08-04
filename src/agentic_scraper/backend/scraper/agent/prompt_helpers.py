import json
import logging
from typing import Any

from agentic_scraper.backend.config.constants import IMPORTANT_FIELDS, MAX_TEXT_FOR_FEWSHOT
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_CONTEXTUAL_HINTS_USED,
    MSG_DEBUG_PROMPT_FALLBACK_MODE,
    MSG_DEBUG_PROMPT_RETRY_MODE,
)
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
Template JSON schema (example fields):
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

These are just illustrative fields. Depending on the context,
extract additional relevant fields that are clearly presented on the page.

"""


def _truncate_fields(fields: dict[str, Any], limit: int = 700) -> str:
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
Your goal is to extract as much useful information
(as structured fields) as possible, from the web page below.
The extraction should be based on the type of the web page (product, blog, job) and its context.
Based on the inferred page type and context, choose the most relevant fields to extract.


Instructions:
- Infer the page_type (e.g. product, blog, job) and context.
- Decide which fields are useful to add to results, based on context.
- Don't limit yourself to common fields (e.g., title, price, author), also extract other
relevant attributes you can infer from the page that would be useful
(e.g., for a product page: product features and specifications, ratings, etc)
- Extract the entire page for semantically meaningful fields as possible.
- If any field is unavailable or missing from the page (e.g., 'Not specified', 'N/A', etc.),
return it as syntactic null. Do not guess or hallucinate values.
- The following fields are especially important:
{", ".join(IMPORTANT_FIELDS)}, but don't hesitate to add more relevant
fields and explore for more fields.
- Return as a valid JSON object.
- If the page includes key-value pairs, such as product specifications,
bullet points, or labeled sections, extract each as a separate field in the JSON output.
And include them as structured field in JSON output, even if they're not
part of the original schema.

Your goal is to extract as much relevant information and more useful fields as possible.


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
    return f"""We previously extracted the following fields from the URL:
{_truncate_fields(best_fields)}

We would like to both recover the following important missing fields,
and explore the page for any additional structured data:
{", ".join(_sort_fields_by_weight(missing_fields)) or "None"}.

Instructions:
- Re-analyze the page carefully.
- Fill in the missing required fields listed above.
- If any field is unavailable or missing from the page (e.g., 'Not specified', 'N/A', etc.),
return it as syntactic null. Do not guess or hallucinate values.
- If previously returned values were null and are still not available on
the page, leave them as null.
- Include any additional relevant or useful fields if not already present.
- Explore all sections of page.
- Use your judgment based on the page type and context to
choose the most relevant fields to extract.
- Don't limit yourself to common fields (e.g., title, price, author), also extract other
relevant attributes you can infer from the page that would be useful
(e.g., for a product page: product features and specifications, ratings, etc)
- Create new field names as needed when encountering novel information.
- If the page includes key-value pairs, such as product specifications,
bullet points, or labeled sections, extract each as a separate field in the JSON output.
And include them as a structured field, even if they're not in the template.

Your goal is to extract as much relevant information and more useful fields as possible.
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
        logger.debug(
            MSG_DEBUG_PROMPT_RETRY_MODE.format(
                url=(best_fields or {}).get("url", "N/A"), missing=missing_fields
            )
        )
        return build_retry_prompt(best_fields or {}, missing_fields)

    if best_fields:
        logger.debug(MSG_DEBUG_PROMPT_FALLBACK_MODE.format(url=best_fields.get("url", "N/A")))
        return f"""We previously extracted the following fields:
{_truncate_fields(best_fields)}

Instructions:
- Analyze the content again and extract any additional useful or contextually relevant fields.
- If possible, improve or extend previously extracted fields (do not just repeat them).
- Use your judgment based on the page type and context, to add more fields.
- Create new field names as needed when encountering novel information.

Return as a valid JSON object.
"""

    return (
        "Analyze the content and extract all useful, relevant, or structured fields. "
        "Use your best judgment to infer fields based on page context and type. "
        "Don't limit yourself to common fields (e.g., title, price, author), also extract other"
        "relevant attributes you can infer from the page that would be useful. "
        "Create new field names as needed when encountering novel information. "
        "Return as a valid JSON object."
    )
