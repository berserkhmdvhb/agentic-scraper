"""
Asynchronous HTML fetcher for scraping pipeline.

This module provides functionality to fetch HTML content from one or more URLs using
`httpx` with support for retries and concurrency limits.

Functions:
- `fetch_url`: Fetch a single URL with retry support.
- `fetch_all`: Fetch multiple URLs concurrently and handle individual errors.

Logging is verbosity-aware: detailed stack traces are logged only when verbose mode is enabled.
"""

import asyncio
import logging

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

from agentic_scraper.config.constants import (
    DEFAULT_HEADERS,
    FETCH_ERROR_PREFIX,
    FETCH_RETRY_DELAY_SECONDS,
)
from agentic_scraper.config.messages import (
    MSG_DEBUG_RETRYING_URL,
    MSG_ERROR_UNEXPECTED_FETCH_EXCEPTION,
    MSG_ERROR_UNREACHABLE_FETCH_URL,
    MSG_INFO_FETCH_SUCCESS,
    MSG_WARNING_FETCH_FAILED,
)
from agentic_scraper.core.settings import Settings

logger = logging.getLogger(__name__)


async def fetch_url(client: httpx.AsyncClient, url: str, *, settings: Settings) -> str:
    """
    Fetch a single URL using the provided AsyncClient and return its HTML content.

    This function supports automatic retries for transient HTTP failures.

    Args:
        client (httpx.AsyncClient): HTTP client used for the request.
        url (str): The target URL to fetch.
        settings (Settings): Global runtime settings, including retry config and timeout.

    Returns:
        str: Raw HTML content returned from the URL.

    Raises:
        httpx.HTTPStatusError: If the request fails and retries are exhausted.
        RuntimeError: If unreachable fallback is hit (should not happen).
    """
    if settings.retry_attempts > 1:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.retry_attempts),
            wait=wait_fixed(FETCH_RETRY_DELAY_SECONDS),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        ):
            with attempt:
                response = await client.get(url, timeout=settings.request_timeout)
                response.raise_for_status()

                if attempt.retry_state.attempt_number > 1:
                    outcome = attempt.retry_state.outcome
                    if outcome and outcome.failed:
                        exc = outcome.exception()
                        logger.debug(
                            MSG_DEBUG_RETRYING_URL.format(
                                url=url,
                                no=attempt.retry_state.attempt_number,
                                exc=exc if exc else "unknown error",
                            )
                        )

                return response.text
    else:
        # Retry disabled or set to 1: only try once
        response = await client.get(url, timeout=settings.request_timeout)
        response.raise_for_status()
        return response.text

    # Safety fallback to appease Ruff (RET503)
    raise RuntimeError(MSG_ERROR_UNREACHABLE_FETCH_URL)


async def fetch_all(
    urls: list[str],
    *,
    settings: Settings,
    concurrency: int,
) -> dict[str, str]:
    """
    Fetch multiple URLs concurrently with a configurable concurrency limit.

    This function uses a semaphore to restrict parallel fetches and collects
    results in a shared dictionary. Failures are prefixed with FETCH_ERROR_PREFIX.

    Args:
        urls (list[str]): List of URLs to fetch.
        settings (Settings): Runtime scraper settings.
        concurrency (int): Max number of concurrent HTTP requests.

    Returns:
        dict[str, str]: Mapping of URL to HTML content or error message.
    """
    results: dict[str, str] = {}
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(headers=DEFAULT_HEADERS, follow_redirects=True) as client:

        async def bounded_fetch(url: str) -> None:
            """
            Fetch a single URL under concurrency control and handle errors.

            Results are written to the shared `results` dictionary with the URL as key.
            """
            async with semaphore:
                try:
                    html = await fetch_url(client, url, settings=settings)
                    results[url] = html
                    logger.info(MSG_INFO_FETCH_SUCCESS.format(url=url))

                except RetryError as e:
                    cause = e.last_attempt.exception()
                    results[url] = f"{FETCH_ERROR_PREFIX}: {cause}"
                    if settings.is_verbose_mode:
                        logger.exception(MSG_ERROR_UNEXPECTED_FETCH_EXCEPTION.format(url=url))
                    else:
                        logger.warning(MSG_WARNING_FETCH_FAILED.format(url=url))

                except (httpx.HTTPError, httpx.RequestError, asyncio.TimeoutError) as e:
                    results[url] = f"{FETCH_ERROR_PREFIX}: {e}"
                    if settings.is_verbose_mode:
                        logger.exception(MSG_WARNING_FETCH_FAILED.format(url=url))
                    else:
                        logger.warning(MSG_WARNING_FETCH_FAILED.format(url=url))

                except Exception as e:
                    results[url] = f"{FETCH_ERROR_PREFIX}: {e}"
                    logger.exception(MSG_ERROR_UNEXPECTED_FETCH_EXCEPTION.format(url=url))

        await asyncio.gather(*(bounded_fetch(url) for url in urls))

    return results
