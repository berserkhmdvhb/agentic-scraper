"""
Asynchronous HTML fetcher for the scraping pipeline.

Responsibilities:
- Fetch HTML content from single or multiple URLs using `httpx`.
- Support retries with exponential backoff for transient errors.
- Enforce concurrency limits and cancellation via `CancelToken`.
- Record structured results keyed by URL with error markers on failure.

Public API:
- `fetch_url`: Fetch a single URL with retry and cancellation support.
- `fetch_all`: Fetch multiple URLs concurrently with bounded concurrency.
- `FetchContext`: Context container used internally by concurrent fetch helpers.

Usage:
    from agentic_scraper.backend.scraper.fetcher import fetch_all

    results = await fetch_all(
        ["https://example.com"],
        settings=settings,
        concurrency=5,
    )

Notes:
- Errors are stored in the results dict prefixed with `FETCH_ERROR_PREFIX`.
- Verbose mode controls whether exceptions are logged with full tracebacks.
- Cancel is cooperative: both asyncio.Event and manual predicates are supported.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

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
from agentic_scraper.backend.scraper.cancel_helpers import (
    CancelToken,
    is_canceled,
)

if TYPE_CHECKING:
    from agentic_scraper.backend.core.settings import Settings

logger = logging.getLogger(__name__)

__all__ = ["FetchContext", "fetch_all", "fetch_url"]


@dataclass
class FetchContext:
    """
    Context object passed to each bounded fetch task.

    Attributes:
        client (httpx.AsyncClient): Shared HTTP client.
        sem (asyncio.Semaphore): Concurrency limiter.
        settings (Settings): Global runtime settings.
        cancel_token (CancelToken | None): Cooperative cancel token.
        results (dict[str, str]): Shared dict to collect results.
    """

    client: httpx.AsyncClient
    sem: asyncio.Semaphore
    settings: Settings
    cancel_token: CancelToken | None
    results: dict[str, str]


def _record_fetch_error(
    results: dict[str, str],
    url: str,
    error: BaseException,
    *,
    settings: Settings,
) -> None:
    """
    Record a fetch error into results and log it appropriately.

    Args:
        results (dict[str, str]): Shared results mapping.
        url (str): Target URL.
        error (BaseException): Exception raised during fetch.
        settings (Settings): Runtime settings to determine verbosity.

    Notes:
        - We stash a readable error string in `results[url]` so the caller can
          surface partial failures without exceptions leaking from the pool.
    """
    if isinstance(error, asyncio.CancelledError):
        results[url] = f"{FETCH_ERROR_PREFIX}: canceled"
        return
    results[url] = f"{FETCH_ERROR_PREFIX}: {error}"
    if settings.is_verbose_mode:
        # Full traceback only in verbose mode; otherwise keep logs concise.
        logger.exception(MSG_ERROR_UNEXPECTED_FETCH_EXCEPTION.format(url=url))
    else:
        logger.warning(MSG_WARNING_FETCH_FAILED.format(url=url))


async def _bounded_fetch(url: str, *, ctx: FetchContext) -> None:
    """
    Fetch one URL under a semaphore, honoring cancellation, and update results.

    Args:
        url (str): Target URL.
        ctx (FetchContext): Shared context object.

    Notes:
        - Cancellation is checked *inside* the semaphore to keep slot accounting
          consistent (task acquires slot → checks cancel → exits quickly if needed).
    """
    async with ctx.sem:  # bound concurrency for all in-flight fetches
        try:
            if is_canceled(ctx.cancel_token):
                # Canonical canceled marker so the caller can distinguish cancellation.
                ctx.results[url] = f"{FETCH_ERROR_PREFIX}: canceled"
                return

            # Translate CancelToken parts for legacy fetch_url signature.
            cancel_event = ctx.cancel_token.event if ctx.cancel_token else None
            should_cancel = ctx.cancel_token.should_cancel if ctx.cancel_token else None

            html = await fetch_url(
                ctx.client,
                url,
                settings=ctx.settings,
                cancel_event=cancel_event,
                should_cancel=should_cancel,
            )
            ctx.results[url] = html
            logger.info(MSG_INFO_FETCH_SUCCESS.format(url=url))

        except RetryError as e:
            # tenacity wraps the last attempt; unwrap for clearer diagnostics.
            exc = e.last_attempt.exception() or RuntimeError("retry failed")
            _record_fetch_error(ctx.results, url, exc, settings=ctx.settings)
        except (httpx.HTTPError, httpx.RequestError, asyncio.TimeoutError) as e:
            _record_fetch_error(ctx.results, url, e, settings=ctx.settings)
        except asyncio.CancelledError as e:
            _record_fetch_error(ctx.results, url, e, settings=ctx.settings)
        except Exception as e:  # noqa: BLE001 - defensive: never crash the pool
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
    Fetch a single URL and return raw HTML.

    Args:
        client (httpx.AsyncClient): HTTP client instance.
        url (str): Target URL to fetch.
        settings (Settings): Runtime settings (timeout, retry config).
        cancel_event (asyncio.Event | None): Event-based cancel signal.
        should_cancel (Callable[[], bool] | None): Predicate-based cancel signal.

    Returns:
        str: Raw HTML content.

    Raises:
        httpx.HTTPStatusError: When the response indicates failure.
        asyncio.CancelledError: When cancel is signaled.
        RuntimeError: Safety fallback if retry logic exits unexpectedly.

    Notes:
        - When `settings.retry_attempts > 1`, we use `tenacity` to retry transient
          errors; `reraise=True` ensures the final exception is visible to callers.
    """
    if settings.retry_attempts > 1:
        # Retry path:
        # tenacity controls attempts, sleeping `FETCH_RETRY_DELAY_SECONDS` between tries.
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.retry_attempts),
            wait=wait_fixed(FETCH_RETRY_DELAY_SECONDS),
            retry=retry_if_exception_type(
                (httpx.HTTPError, httpx.RequestError, asyncio.TimeoutError)
            ),
            reraise=True,  # bubble the last failure to our except blocks
        ):
            with attempt:
                # Pre-attempt cancel keeps responsiveness high during backoffs.
                if (cancel_event and cancel_event.is_set()) or (should_cancel and should_cancel()):
                    raise asyncio.CancelledError

                # Single request attempt with per-request timeout from settings.
                response = await client.get(url, timeout=settings.request_timeout)
                response.raise_for_status()

                # If this is a subsequent attempt, log a debug breadcrumb with the last failure.
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
        # Single-shot path: no retries configured.
        if (cancel_event and cancel_event.is_set()) or (should_cancel and should_cancel()):
            raise asyncio.CancelledError
        response = await client.get(url, timeout=settings.request_timeout)
        response.raise_for_status()
        return response.text

    # Control should not reach here; keep a defensive fallback for linters/type-checkers.
    raise RuntimeError(MSG_ERROR_UNREACHABLE_FETCH_URL)


async def fetch_all(
    urls: list[str],
    *,
    settings: Settings,
    concurrency: int,
    cancel: CancelToken | None = None,
    client_factory: Callable[..., httpx.AsyncClient] | None = None,
) -> dict[str, str]:
    """
    Fetch multiple URLs concurrently with cooperative cancellation.

    Args:
        urls (list[str]): Target URLs.
        settings (Settings): Runtime settings.
        concurrency (int): Maximum simultaneous requests (min=1).
        cancel (CancelToken | None): Optional cancel token.
        client_factory (Callable[..., httpx.AsyncClient] | None): Optional factory
            for testing/injection.

    Returns:
        dict[str, str]: Mapping of URL → HTML or error string.

    Notes:
        - Tasks are created for each URL; a shared semaphore enforces the real
          concurrency limit.
        - On cancellation, we cancel outstanding tasks and drain them with
          `return_exceptions=True` to avoid surfacing CancelledError to callers.
    """
    if not urls:  # trivial fast-path avoids spinning up a client
        return {}

    results: dict[str, str] = {}
    sem = asyncio.Semaphore(max(1, int(concurrency)))  # clamp to >= 1 to avoid deadlock

    # Allow injection of a custom client (e.g., MockTransport) for tests.
    factory = client_factory or (lambda **kw: httpx.AsyncClient(**kw))

    async with factory(headers=DEFAULT_HEADERS, follow_redirects=True) as client:
        ctx = FetchContext(
            client=client,
            sem=sem,
            settings=settings,
            cancel_token=cancel,
            results=results,
        )

        # Schedule bounded fetch tasks; naming aids debugging in task dumps.
        tasks = [
            asyncio.create_task(_bounded_fetch(url, ctx=ctx), name=f"fetch:{i}")
            for i, url in enumerate(urls)
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            # If a cancel arrived mid-flight, propagate and drain.
            if is_canceled(cancel):
                for t in tasks:
                    if not t.done():
                        t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    return results
