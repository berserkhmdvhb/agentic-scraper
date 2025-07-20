import asyncio
import logging

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from agentic_scraper.backend.config.constants import (
    FETCH_RETRY_ATTEMPTS,
    FETCH_RETRY_DELAY_SECONDS,
)
from agentic_scraper.backend.config.messages import (
    MSG_FETCH_ERROR_PREFIX,
    MSG_INFO_FETCH_SUCCESS,
    MSG_WARNING_FETCH_FAILED,
)
from agentic_scraper.backend.core.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(FETCH_RETRY_ATTEMPTS),
    wait=wait_fixed(FETCH_RETRY_DELAY_SECONDS),
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
    """
    results: dict[str, str] = {}
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(follow_redirects=True) as client:

        async def bounded_fetch(url: str) -> None:
            async with semaphore:
                try:
                    html = await fetch_url(client, url)
                    results[url] = html
                    logger.info(MSG_INFO_FETCH_SUCCESS.format(url))
                except (httpx.HTTPError, httpx.RequestError, asyncio.TimeoutError) as e:
                    results[url] = f"{MSG_FETCH_ERROR_PREFIX}: {e}"
                    logger.warning("%s: %s (%s)", MSG_WARNING_FETCH_FAILED, url, e)

        await asyncio.gather(*(bounded_fetch(url) for url in urls))

    return results
