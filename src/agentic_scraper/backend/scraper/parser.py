"""
HTML metadata and text parser utilities for Agentic Scraper.

Responsibilities:
- Parse *visible* page text from raw HTML (for downstream LLM summarization).
- Extract lightweight metadata from documents: `<title>`, meta description, author.
- Emit sampled debug logs in verbose mode to aid troubleshooting.

Public API:
- `extract_main_text(html)`: Return cleaned, visible page text.
- `extract_title_from_soup(soup, settings)`: Read `<title>` content.
- `extract_meta_description_from_soup(soup, settings)`: Read `<meta name="description">`.
- `extract_author_from_soup(soup, settings)`: Read common author meta tags.
- `parse_all_metadata(html, settings)`: Convenience aggregate for common fields.

Operational:
- Concurrency: Pure CPU-bound parsing; no network I/O.
- Caching/TTL: None.
- Logging: Uses `settings.is_verbose_mode` to toggle debug detail; otherwise info-level fallbacks.

Usage:
    from bs4 import BeautifulSoup
    from agentic_scraper.backend.core.settings import get_settings
    from agentic_scraper.backend.scraper.parser import (
        extract_main_text, parse_all_metadata
    )

    settings = get_settings()
    text = extract_main_text(html_str)
    meta = parse_all_metadata(html_str, settings)

Notes:
- These helpers intentionally avoid heavy readability heuristics to keep them fast and predictable.
- If you need richer extraction (e.g., OpenGraph/Twitter cards), add dedicated helpers rather than
  overloading the existing ones.
"""

import logging

from bs4 import BeautifulSoup
from bs4.element import Tag

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_PARSED_AUTHOR,
    MSG_DEBUG_PARSED_META_DESCRIPTION,
    MSG_DEBUG_PARSED_TITLE,
    MSG_INFO_NO_AUTHOR,
    MSG_INFO_NO_META_DESCRIPTION,
    MSG_INFO_NO_TITLE,
)
from agentic_scraper.backend.core.settings import Settings

__all__ = [
    "extract_author_from_soup",
    "extract_main_text",
    "extract_meta_description_from_soup",
    "extract_title_from_soup",
    "parse_all_metadata",
]

logger = logging.getLogger(__name__)


def extract_main_text(html: str) -> str:
    """
    Extract main, visible text content from HTML for LLM summarization.

    Strips non-content tags like `<script>`, `<style>`, and `<noscript>`, then
    collapses whitespace while preserving line boundaries.

    Args:
        html (str): Raw HTML source of the page.

    Returns:
        str: Visible body text with newlines preserved (no HTML tags).

    Examples:
        text = extract_main_text("<html><body><h1>Title</h1><script>x</script></body></html>")
        # -> "Title"

    Notes:
        - This is a lightweight heuristic (no DOM scoring); it is fast and predictable.
        - Use a separator of `\\n` to keep logical line breaks across block elements.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Drop non-visible/irrelevant elements early to reduce noise in extracted text.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Extract text with line separators, then trim and remove blank lines.
    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)


def extract_title_from_soup(soup: BeautifulSoup, settings: Settings) -> str | None:
    """
    Extract the page title from a `BeautifulSoup` document.

    Looks for the `<title>` tag and returns its trimmed text if found.

    Args:
        soup (BeautifulSoup): Parsed HTML document.
        settings (Settings): Runtime settings (used to toggle debug logging).

    Returns:
        str | None: Page title if present; otherwise `None`.

    Notes:
        - Logs at DEBUG only in verbose mode to avoid leaking content in normal ops.
    """
    title_tag = soup.find("title")
    if isinstance(title_tag, Tag):
        title = title_tag.text.strip()
        if settings.is_verbose_mode:
            logger.debug(MSG_DEBUG_PARSED_TITLE.format(title=title))
        return title
    # Keep an info-level breadcrumb so missing titles are observable in aggregates.
    logger.info(MSG_INFO_NO_TITLE)
    return None


def extract_meta_description_from_soup(soup: BeautifulSoup, settings: Settings) -> str | None:
    """
    Extract the meta description from a `BeautifulSoup` document.

    Searches for `<meta name="description">` and returns its trimmed `content` value.

    Args:
        soup (BeautifulSoup): Parsed HTML document.
        settings (Settings): Runtime settings (used to toggle debug logging).

    Returns:
        str | None: Meta description if found; otherwise `None`.

    Notes:
        - We intentionally do not check OpenGraph/Twitter description here; keep this focused.
    """
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_tag, Tag):
        content = meta_tag.get("content", "")
        if isinstance(content, str):
            description = content.strip()
            if settings.is_verbose_mode:
                logger.debug(MSG_DEBUG_PARSED_META_DESCRIPTION.format(description=description))
            return description
    logger.info(MSG_INFO_NO_META_DESCRIPTION)
    return None


def extract_author_from_soup(soup: BeautifulSoup, settings: Settings) -> str | None:
    """
    Attempt to extract an author value from common meta tags.

    Tries a small set of well-known attributes: `"author"`, `"article:author"`, `"byline"`.

    Args:
        soup (BeautifulSoup): Parsed HTML document.
        settings (Settings): Runtime settings (used to toggle debug logging).

    Returns:
        str | None: Author value if found; otherwise `None`.

    Notes:
        - Sites are inconsistent with author metadata; this is a best-effort utility.
    """
    # Prefer small, explicit candidates to keep the logic predictable and fast.
    candidates = [{"name": "author"}, {"property": "article:author"}, {"name": "byline"}]
    for attr in candidates:
        tag = soup.find("meta", attrs=attr)
        if isinstance(tag, Tag):
            content = tag.get("content")
            if isinstance(content, str):
                author = content.strip()
                if settings.is_verbose_mode:
                    logger.debug(MSG_DEBUG_PARSED_AUTHOR.format(source=attr, author=author))
                return author
    logger.info(MSG_INFO_NO_AUTHOR)
    return None


def parse_all_metadata(html: str, settings: Settings) -> dict[str, str | None]:
    """
    Parse common metadata fields (title, description, author) from an HTML string.

    Internally constructs a `BeautifulSoup` object once and runs the individual
    extractors to avoid reparsing.

    Args:
        html (str): Raw HTML content of the page.
        settings (Settings): Runtime settings (used to toggle debug logging).

    Returns:
        dict[str, str | None]: Dict with keys: `title`, `description`, `author`.

    Examples:
        meta = parse_all_metadata(html, settings)
        # -> {"title": "...", "description": "...", "author": None}
    """
    # Single parse pass; downstream extractors share the same soup instance.
    soup = BeautifulSoup(html, "html.parser")
    return {
        "title": extract_title_from_soup(soup, settings),
        "description": extract_meta_description_from_soup(soup, settings),
        "author": extract_author_from_soup(soup, settings),
    }
