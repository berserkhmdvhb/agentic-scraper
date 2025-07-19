import asyncio
import logging

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from agentic_scraper.backend.config.messages import (
    MSG_FETCH_ERROR_PREFIX,
    MSG_INFO_FETCH_SUCCESS,
    MSG_WARNING_FETCH_FAILED,
)
from agentic_scraper.backend.core.settings import load_settings

settings = load_settings()
logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(1),
    retry=retry_if_exception_type(httpx.HTTPError),
)
async def fetch_url(client: httpx.AsyncClient, url: str) -> str:
    """
    Fetch a single URL using the provided AsyncClient and return its HTML content.

    Retries up to 3 times on transient HTTP errors using tenacity.

    Args:
        client (httpx.AsyncClient): The async HTTP client to use for the request.
        url (str): The target URL to fetch.

    Returns:
        str: Raw HTML content of the fetched page.

    Raises:
        httpx.HTTPError: If the request fails after retries.
    """
    response = await client.get(url, timeout=settings.request_timeout)
    response.raise_for_status()
    return response.text


async def fetch_all(
    urls: list[str], concurrency: int = settings.max_concurrent_requests
) -> dict[str, str]:
    """
    Fetch multiple URLs concurrently with a configurable concurrency limit.

    Each URL is fetched using `fetch_url`, and results are collected in a dictionary
    keyed by URL. If a fetch fails, the corresponding value will be a string prefixed
    with MSG_FETCH_ERROR_PREFIX and the error message.

    Args:
        urls (list[str]): List of URLs to fetch.
        concurrency (int): Maximum number of concurrent fetch operations.

    Returns:
        dict[str, str]: A mapping from each input URL to either its HTML content
                        (on success) or a prefixed error message (on failure).
    """
    results: dict[str, str] = {}
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(follow_redirects=True) as client:

        async def bounded_fetch(url: str) -> None:
            async with semaphore:
                try:
                    html = await fetch_url(client, url)
                    results[url] = html
                    logger.info(MSG_INFO_FETCH_SUCCESS, url)
                except (httpx.HTTPError, httpx.RequestError, asyncio.TimeoutError) as e:
                    results[url] = f"{MSG_FETCH_ERROR_PREFIX}: {e}"
                    logger.warning(MSG_WARNING_FETCH_FAILED, url, e)

        await asyncio.gather(*(bounded_fetch(url) for url in urls))

    return results
