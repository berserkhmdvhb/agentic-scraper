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

logger = logging.getLogger(__name__)


def extract_main_text(html: str) -> str:
    """
    Extract main visible text content from HTML for LLM summarization.

    Args:
        html (str): Raw HTML content as a string.

    Returns:
        str: Cleaned and de-scripted visible text content.
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)


def extract_title_from_soup(soup: BeautifulSoup) -> str | None:
    """
    Extract the <title> tag content from a BeautifulSoup object.

    Args:
        soup (BeautifulSoup): Parsed HTML content.

    Returns:
        str | None: The title of the page, or None if not found.
    """
    title_tag = soup.find("title")
    if isinstance(title_tag, Tag):
        title = title_tag.text.strip()
        logger.debug(MSG_DEBUG_PARSED_TITLE, title)
        return title
    logger.info(MSG_INFO_NO_TITLE)
    return None


def extract_meta_description_from_soup(soup: BeautifulSoup) -> str | None:
    """
    Extract the meta description from a BeautifulSoup object if present.

    Args:
        soup (BeautifulSoup): Parsed HTML content.

    Returns:
        str | None: Meta description content, or None if not found.
    """
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_tag, Tag):
        content = meta_tag.get("content", "")
        if isinstance(content, str):
            description = content.strip()
            logger.debug(MSG_DEBUG_PARSED_META_DESCRIPTION, description)
            return description
    logger.info(MSG_INFO_NO_META_DESCRIPTION)
    return None


def extract_author_from_soup(soup: BeautifulSoup) -> str | None:
    """
    Attempt to extract the author's name from known meta tags in a BeautifulSoup object.

    Args:
        soup (BeautifulSoup): Parsed HTML content.

    Returns:
        str | None: The author's name if found, else None.
    """
    candidates = [{"name": "author"}, {"property": "article:author"}, {"name": "byline"}]
    for attr in candidates:
        tag = soup.find("meta", attrs=attr)
        if isinstance(tag, Tag):
            content = tag.get("content")
            if isinstance(content, str):
                author = content.strip()
                logger.debug(MSG_DEBUG_PARSED_AUTHOR, attr, author)
                return author
    logger.info(MSG_INFO_NO_AUTHOR)
    return None


def parse_all_metadata(html: str) -> dict[str, str | None]:
    """
    Parse common metadata fields from an HTML document.

    Args:
        html (str): Raw HTML content.

    Returns:
        dict[str, str | None]: Parsed title, description, and author.
    """
    soup = BeautifulSoup(html, "html.parser")
    return {
        "title": extract_title_from_soup(soup),
        "description": extract_meta_description_from_soup(soup),
        "author": extract_author_from_soup(soup),
    }
