from bs4 import BeautifulSoup
from bs4.element import Tag


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


def extract_title(html: str) -> str | None:
    """
    Extract the <title> tag content from the HTML document.

    Args:
        html (str): Raw HTML content.

    Returns:
        str | None: The title of the page, or None if not found.
    """
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    if isinstance(title_tag, Tag):
        return title_tag.text.strip()
    return None


def extract_meta_description(html: str) -> str | None:
    """
    Extract the meta description from HTML if present.

    Args:
        html (str): Raw HTML content.

    Returns:
        str | None: Meta description content, or None if not found.
    """
    soup = BeautifulSoup(html, "html.parser")
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_tag, Tag):
        content = meta_tag.get("content", "")
        if isinstance(content, str):
            return content.strip()
    return None


def extract_author(html: str) -> str | None:
    """
    Attempt to extract the author's name from known meta tags.

    Args:
        html (str): Raw HTML content.

    Returns:
        str | None: The author's name if found, else None.
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates = [{"name": "author"}, {"property": "article:author"}, {"name": "byline"}]
    for attr in candidates:
        tag = soup.find("meta", attrs=attr)
        if isinstance(tag, Tag):
            content = tag.get("content")
            if isinstance(content, str):
                return content.strip()
    return None
