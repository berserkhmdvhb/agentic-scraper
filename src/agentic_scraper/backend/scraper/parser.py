"""
HTML metadata and text parser for AgenticScraper.

This module provides utilities for parsing structured content from raw HTML,
including:
- Cleaned main body text for LLM summarization.
- Metadata fields: <title>, meta description, and author.

Logging is enabled for verbose mode to help trace parsed fields.
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

logger = logging.getLogger(__name__)


def extract_main_text(html: str) -> str:
    """
    Extract main visible text content from HTML for LLM summarization.

    Strips non-content tags like <script> and <style>, and returns a cleaned string.

    Args:
        html (str): Raw HTML source of the page.

    Returns:
        str: Visible body text with newlines preserved.
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)


def extract_title_from_soup(soup: BeautifulSoup, settings: Settings) -> str | None:
    """
    Extract the page title from a BeautifulSoup object.

    Looks for the <title> tag and returns its trimmed text if found.

    Args:
        soup (BeautifulSoup): Parsed HTML document.
        settings (Settings): Global runtime settings for logging verbosity.

    Returns:
        str | None: Page title if found, else None.
    """
    title_tag = soup.find("title")
    if isinstance(title_tag, Tag):
        title = title_tag.text.strip()
        if settings.is_verbose_mode:
            logger.debug(MSG_DEBUG_PARSED_TITLE.format(title=title))
        return title
    logger.info(MSG_INFO_NO_TITLE)
    return None


def extract_meta_description_from_soup(soup: BeautifulSoup, settings: Settings) -> str | None:
    """
    Extract the meta description from a BeautifulSoup object.

    Looks for a <meta name="description"> tag and returns its trimmed "content" value
    if available.

    Args:
        soup (BeautifulSoup): Parsed HTML document.
        settings (Settings): Global runtime settings for logging verbosity.

    Returns:
        str | None: Meta description content if found, else None.
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
    Attempt to extract the author's name from known meta tags in a BeautifulSoup object.

    Tries a list of common author-related meta tag attributes such as "author",
    "article:author", and "byline".

    Args:
        soup (BeautifulSoup): Parsed HTML document.
        settings (Settings): Global runtime settings for logging verbosity.

    Returns:
        str | None: Author name if found, else None.
    """
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
    Parse common metadata fields (title, description, author) from an HTML document.

    Internally parses the HTML into a BeautifulSoup object and applies individual
    extractors for each supported field.

    Args:
        html (str): Raw HTML content of the page.
        settings (Settings): Global runtime settings for logging verbosity.

    Returns:
        dict[str, str | None]: Dictionary with keys 'title', 'description', and 'author'.
                               Each value may be None if not found.
    """
    soup = BeautifulSoup(html, "html.parser")
    return {
        "title": extract_title_from_soup(soup, settings),
        "description": extract_meta_description_from_soup(soup, settings),
        "author": extract_author_from_soup(soup, settings),
    }
