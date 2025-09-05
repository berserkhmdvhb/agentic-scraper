"""
Prompt construction utilities for LLM-based scraping agents.

Responsibilities:
- Build first-attempt prompts (simple/enhanced) that guide the LLM to extract
  structured fields from page content.
- Build retry prompts that focus the LLM on missing fields while encouraging
  discovery of additional relevant data.
- Provide a fallback prompt when there are no clearly-missing required fields.

Public API:
- `build_prompt`: Construct an initial prompt (style: 'simple' | 'enhanced').
- `build_retry_prompt`: Construct a focused retry prompt around missing fields.
- `build_retry_or_fallback_prompt`: Choose retry or generic fallback prompt.

Operational:
- Logging: Debug logs annotate which mode/context was used (no PII).
- Token economy: The enhanced prompt includes optional context hints and a few-shot
  example only when the input text is short enough (see `MAX_TEXT_FOR_FEWSHOT`).

Usage:
    from agentic_scraper.backend.scraper.agents.prompt_helpers import build_prompt

    prompt = build_prompt(
        text=clean_text,
        url="https://example.com/x",
        prompt_style="enhanced",
        context_hints={"page": "product", "breadcrumbs": "Home > Gadgets"},
    )

Notes:
- The prompt intentionally encourages discovery of additional useful fields beyond
  the minimal schema — this helps adaptive agents enrich outputs when the page
  contains structured sections (specs, bullets, labels, etc.).
"""

import json
import logging
from typing import Any

from agentic_scraper.backend.config.constants import IMPORTANT_FIELDS, MAX_TEXT_FOR_FEWSHOT
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_CONTEXTUAL_HINTS_USED,
    MSG_DEBUG_PROMPT_FALLBACK_MODE,
    MSG_DEBUG_PROMPT_RETRY_MODE,
)
from agentic_scraper.backend.scraper.agents.field_utils import FIELD_WEIGHTS

logger = logging.getLogger(__name__)

__all__ = ["build_prompt", "build_retry_or_fallback_prompt", "build_retry_prompt"]

# A short illustrative example that helps steer the model when the input text is short
# enough (we avoid adding it to long prompts to control token usage).
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

# A lightweight schema “shape” reminder to encourage structured output without being
# overly prescriptive — the agent is free to add more fields when it makes sense.
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
    """
    Render a compact, pretty-printed JSON preview of fields with a hard length cap.

    Args:
        fields (dict[str, Any]): Dict to be previewed inside a prompt.
        limit (int): Maximum number of characters to include.

    Returns:
        str: Possibly truncated JSON with a sentinel suffix.

    Notes:
        - Keeps retry prompts concise while still showing prior results.
    """
    raw = json.dumps(fields, indent=2)
    return raw if len(raw) <= limit else raw[:limit] + "\n... (truncated)"


def _sort_fields_by_weight(fields: set[str]) -> list[str]:
    """
    Order field names by their project-defined importance weights (desc).

    Args:
        fields (set[str]): Field names.

    Returns:
        list[str]: Sorted field names (heaviest first).

    Notes:
        - Uses FIELD_WEIGHTS; unknown fields default to weight 0.
    """
    return sorted(fields, key=lambda f: FIELD_WEIGHTS.get(f, 0), reverse=True)


def build_prompt(
    text: str,
    url: str,
    prompt_style: str = "simple",
    context_hints: dict[str, str] | None = None,
) -> str:
    """
    Build the first-attempt prompt for the LLM, optionally enriched with context hints.

    Args:
        text (str): Cleaned page text (already extracted from HTML).
        url (str): The page URL (echoed in the prompt).
        prompt_style (str): 'simple' | 'enhanced'. The 'enhanced' style includes
            optional context hints (page type/meta/breadcrumbs/URL segments) and,
            when the text is short, a small few-shot example.
        context_hints (dict[str, str] | None): Optional hints from HTML/URL analysis.
            Expected keys include: "page", "meta", "breadcrumbs", "url_segments".

    Returns:
        str: A fully constructed prompt string.

    Notes:
        - We deliberately encourage extraction beyond a minimal schema to capture
          labeled sections like specs, bullet lists, etc.
        - The input text is clipped to ~4k characters as a conservative token guard.
    """
    # Base instruction block shared by both prompt styles.
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

    # Enhanced prompt optionally includes extracted hints; this helps the LLM
    # quickly specialize the schema without spending tokens re-deriving context.
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
        # Add a tiny few-shot only when the text is short, to limit token overhead.
        example_block = FEW_SHOT_EXAMPLE if len(text) < MAX_TEXT_FOR_FEWSHOT else ""
    else:
        context_block = ""
        example_block = ""

    # Final prompt assembly. We clip the text to avoid overly large prompts.
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
    Build a retry prompt that focuses on missing fields while inviting enrichment.

    Args:
        best_fields (dict[str, Any]): Partial output from a prior attempt.
        missing_fields (set[str]): Required fields that the model failed to extract.

    Returns:
        str: A retry instruction string.

    Notes:
        - Includes a compact preview of prior fields (truncated).
        - Orders missing fields by importance to improve signal-to-noise.
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
    Choose between a focused retry prompt (if fields are missing) or a generic fallback.

    Args:
        best_fields (dict[str, Any] | None): Previously extracted fields, if any.
        missing_fields (set[str]): Required fields not present in the last result.

    Returns:
        str: Retry or fallback prompt.

    Notes:
        - Emits debug logs indicating which path is taken; helps test determinism.
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

    # No prior fields and nothing explicitly missing — ask for broad, structured extraction.
    return (
        "Analyze the content and extract all useful, relevant, or structured fields. "
        "Use your best judgment to infer fields based on page context and type. "
        "Don't limit yourself to common fields (e.g., title, price, author), also extract other"
        " relevant attributes you can infer from the page that would be useful. "
        "Create new field names as needed when encountering novel information. "
        "Return as a valid JSON object."
    )
