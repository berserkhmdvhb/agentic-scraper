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
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

from agentic_scraper.backend.config.constants import (
    DEFAULT_HEADERS,
    FETCH_ERROR_PREFIX,
    FETCH_RETRY_DELAY_SECONDS,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_RETRYING_URL,
    MSG_ERROR_UNEXPECTED_FETCH_EXCEPTION,
    MSG_ERROR_UNREACHABLE_FETCH_URL,
    MSG_INFO_FETCH_SUCCESS,
    MSG_WARNING_FETCH_FAILED,
)
from agentic_scraper.backend.core.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class FetchContext:
    client: httpx.AsyncClient
    sem: asyncio.Semaphore
    settings: Settings
    cancel_event: asyncio.Event | None
    should_cancel: Callable[[], bool] | None
    results: dict[str, str]


def _is_canceled(
    cancel_event: asyncio.Event | None,
    should_cancel: Callable[[], bool] | None,
) -> bool:
    """Return True if either the event is set or the predicate requests cancel."""
    if cancel_event and cancel_event.is_set():
        return True
    if should_cancel:
        try:
            return bool(should_cancel() is not None)
        except Exception as e:  # noqa: BLE001
            # Fail-open: log but default to not canceled
            logger.debug("should_cancel() raised %r, ignoring", e)
            return False
    return False


def _record_fetch_error(
    results: dict[str, str],
    url: str,
    error: BaseException,
    *,
    settings: Settings,
) -> None:
    """Record an error into results with verbosity-aware logging."""
    if isinstance(error, asyncio.CancelledError):
        results[url] = f"{FETCH_ERROR_PREFIX}: canceled"
        return
    results[url] = f"{FETCH_ERROR_PREFIX}: {error}"
    if settings.is_verbose_mode:
        logger.exception(MSG_ERROR_UNEXPECTED_FETCH_EXCEPTION.format(url=url))
    else:
        logger.warning(MSG_WARNING_FETCH_FAILED.format(url=url))


async def _bounded_fetch(
    url: str,
    *,
    ctx: FetchContext,
) -> None:
    """Fetch one URL under semaphore; honor cancel; store result or error."""
    async with ctx.sem:
        try:
            if _is_canceled(ctx.cancel_event, ctx.should_cancel):
                ctx.results[url] = f"{FETCH_ERROR_PREFIX}: canceled"
                return

            html = await fetch_url(
                ctx.client,
                url,
                settings=ctx.settings,
                cancel_event=ctx.cancel_event,
                should_cancel=ctx.should_cancel,
            )
            ctx.results[url] = html
            logger.info(MSG_INFO_FETCH_SUCCESS.format(url=url))

        except RetryError as e:
            exc = e.last_attempt.exception() or RuntimeError("retry failed")
            _record_fetch_error(ctx.results, url, exc, settings=ctx.settings)
        except (httpx.HTTPError, httpx.RequestError, asyncio.TimeoutError) as e:
            _record_fetch_error(ctx.results, url, e, settings=ctx.settings)
        except asyncio.CancelledError as e:
            _record_fetch_error(ctx.results, url, e, settings=ctx.settings)
        except Exception as e:  # noqa: BLE001 - last-resort logging to avoid task crashing the pool
            _record_fetch_error(ctx.results, url, e, settings=ctx.settings)


async def fetch_url(
    client: httpx.AsyncClient,
    url: str,
    *,
    settings: Settings,
    cancel_event: asyncio.Event | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> str:
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
            retry=retry_if_exception_type(
                (httpx.HTTPError, httpx.RequestError, asyncio.TimeoutError)
            ),
            reraise=True,
        ):
            with attempt:
                # Short-circuit before each attempt on cancel
                event_canceled = cancel_event and cancel_event.is_set()
                manual_canceled = should_cancel and should_cancel()
                if event_canceled or manual_canceled:
                    raise asyncio.CancelledError
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
        event_canceled = cancel_event and cancel_event.is_set()
        manual_canceled = should_cancel and should_cancel()
        if event_canceled or manual_canceled:
            raise asyncio.CancelledError
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
    cancel_event: asyncio.Event | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, str]:
    """
    Fetch multiple URLs concurrently with a configurable concurrency limit.

    Returns:
        dict[str, str]: Mapping of URL to HTML or error (prefixed with FETCH_ERROR_PREFIX).
    """
    if not urls:
        return {}

    results: dict[str, str] = {}
    sem = asyncio.Semaphore(max(1, int(concurrency)))

    async with httpx.AsyncClient(headers=DEFAULT_HEADERS, follow_redirects=True) as client:
        ctx = FetchContext(
            client=client,
            sem=sem,
            settings=settings,
            cancel_event=cancel_event,
            should_cancel=should_cancel,
            results=results,
        )

        tasks = [
            asyncio.create_task(_bounded_fetch(url, ctx=ctx), name=f"fetch:{i}")
            for i, url in enumerate(urls)
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            # Ensure pending tasks are cancelled if an external cancel arrives mid-flight
            if _is_canceled(cancel_event, should_cancel):
                for t in tasks:
                    if not t.done():
                        t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    return results
