import logging
from typing import Literal

from agentic_scraper.backend.config.constants import IMPORTANT_FIELDS, MAX_TEXT_FOR_FEWSHOT

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


def build_prompt(
    text: str,
    url: str,
    context_hints: dict[str, str] | None = None,
    *,
    prompt_style: Literal["simple", "enhanced"] = "simple",
) -> str:
    """
    Build a structured prompt for LLM content extraction based on the chosen style.

    Args:
        text (str): The visible HTML text to analyze.
        url (str): The source page URL.
        context_hints (dict | None): Optional metadata like meta tags or breadcrumbs.
        prompt_style (str): Choose between "simple" and "enhanced".

    Returns:
        str: The full LLM prompt string.
    """
    if prompt_style == "simple":
        return f"""
You are a smart web content extraction agent.

Analyze the content of the page provided below and return a structured JSON object
containing the most relevant information.

You must:
- Infer the page type (e.g. blog, product, job ad, article).
- Extract appropriate fields based on that type.
- Only include fields that are **explicitly present** in the text.
- Return **valid JSON only**, no markdown or explanation.

Common fields per type include:
- Blog: title, author, date, tags, summary
- Product: title, price, brand, availability, features
- Job ad: job_title, company, location, salary, requirements
- Article: headline, author, published_date, summary, tags

Always include:
- url: the original URL of the page
- page_type: a short label for the type of page (e.g. "product", "blog")

Page URL: {url}

Page Content:
{text[:4000]}
""".strip()

    # Enhanced prompt with context
    meta = context_hints.get("meta") if context_hints else "N/A"
    breadcrumbs = context_hints.get("breadcrumbs") if context_hints else "N/A"
    url_segments = context_hints.get("url_segments") if context_hints else "N/A"

    context_block = f"""
Extra context:
- Meta tags: {meta}
- Breadcrumbs: {breadcrumbs}
- URL segments: {url_segments}
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
