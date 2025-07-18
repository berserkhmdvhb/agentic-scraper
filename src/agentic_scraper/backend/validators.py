from urllib.parse import urlparse


def is_valid_url(url: str) -> bool:
    """
    Check if a given string is a valid HTTP/HTTPS URL.

    Args:
        url (str): The URL to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def clean_input_urls(raw: str) -> list[str]:
    """
    Process raw input text (from textarea or file) into a list of cleaned URLs.

    Args:
        raw (str): Multi-line string with one or more URLs.

    Returns:
        list[str]: List of valid, stripped URLs.
    """
    lines = raw.strip().splitlines()
    cleaned = [line.strip() for line in lines if line.strip()]
    return [url for url in cleaned if is_valid_url(url)]


def deduplicate_urls(urls: list[str]) -> list[str]:
    """
    Remove duplicate URLs while preserving order.

    Args:
        urls (list[str]): Input list of URLs.

    Returns:
        list[str]: Unique URLs in original order.
    """
    seen = set()
    result = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def filter_successful(results: dict[str, str]) -> dict[str, str]:
    """
    Filter out URLs where fetching failed (error string prefixed with __FETCH_ERROR__).

    Args:
        results (dict[str, str]): Map of url → html or error message.

    Returns:
        dict[str, str]: Only successfully fetched URLs.
    """
    return {url: html for url, html in results.items() if not html.startswith("__FETCH_ERROR__")}
