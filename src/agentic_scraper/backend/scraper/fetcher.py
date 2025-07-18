import asyncio
import logging

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from agentic_scraper.backend.core.settings import settings

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
    """
    response = await client.get(url, timeout=settings.request_timeout)
    response.raise_for_status()
    return response.text


async def fetch_all(
    urls: list[str], concurrency: int = settings.max_concurrent_requests
) -> dict[str, str]:
    """
    Fetch multiple URLs concurrently with a configurable concurrency limit.

    Returns a mapping of URL to HTML content or error string.
    Errors are prefixed with '__FETCH_ERROR__'.
    """
    results: dict[str, str] = {}
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(follow_redirects=True) as client:

        async def bounded_fetch(url: str) -> None:
            async with semaphore:
                try:
                    html = await fetch_url(client, url)
                    results[url] = html
                    logger.info("Fetched %s successfully", url)
                except Exception as e:
                    results[url] = f"__FETCH_ERROR__: {e}"
                    logger.warning("Failed to fetch %s: %s", url, e)

        await asyncio.gather(*(bounded_fetch(url) for url in urls))

    return results
