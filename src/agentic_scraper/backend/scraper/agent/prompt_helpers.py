import logging

from agentic_scraper.backend.config.constants import IMPORTANT_FIELDS, MAX_TEXT_FOR_FEWSHOT
from agentic_scraper.backend.config.messages import MSG_DEBUG_CONTEXTUAL_HINTS_USED

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
"""


def build_enhanced_prompt(text: str, url: str, context_hints: dict[str, str]) -> str:
    """Construct a detailed LLM prompt with context, schema, and optional few-shot example."""
    meta = context_hints.get("meta")
    breadcrumbs = context_hints.get("breadcrumbs")
    url_segments = context_hints.get("url_segments")

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
- Meta tags: {meta or "N/A"}
- Breadcrumbs: {breadcrumbs or "N/A"}
- URL segments: {url_segments or "N/A"}
"""

    example_block = FEW_SHOT_EXAMPLE if len(text) < MAX_TEXT_FOR_FEWSHOT else ""

    return f"""
You are a smart web content extraction agent.

Your goal is to extract structured metadata from the web page below
for use in a structured dataset or search engine.

Instructions:
- Infer the page_type (e.g. product, blog, job).
- Choose fields based on type.
- Only extract values present in the page.
- Prioritize extracting important fields: {", ".join(IMPORTANT_FIELDS)}.
- Return only valid JSON.

Mandatory fields: url, page_type.
{SCHEMA_BLOCK}
{example_block}
{context_block}

Page URL: {url}

Page Content:
{text[:4000]}
""".strip()
