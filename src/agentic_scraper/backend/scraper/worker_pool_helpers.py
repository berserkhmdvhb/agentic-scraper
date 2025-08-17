"""
Helper functions for the asynchronous worker pool.

These are factored out of worker_pool.py to reduce complexity in the worker()
coroutine while preserving behavior, logging, and message-constant usage.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_POOL_ENQUEUED_URL,
    MSG_DEBUG_WORKER_CREATED_REQUEST,
    MSG_DEBUG_WORKER_GOT_ITEM,
    MSG_DEBUG_WORKER_ITEM_APPENDED,
    MSG_DEBUG_WORKER_NO_ITEM,
    MSG_DEBUG_WORKER_PICKED_URL,
    MSG_DEBUG_WORKER_PROGRESS,
    MSG_ERROR_WORKER_FAILED,
    MSG_WARNING_ON_ERROR_CALLBACK_FAILED,
    MSG_WARNING_ON_ITEM_PROCESSED_FAILED,
    MSG_WARNING_PROGRESS_CALLBACK_FAILED,
    MSG_WARNING_WORKER_FAILED_SHORT,
)

if TYPE_CHECKING:
    from agentic_scraper.backend.config.aliases import ScrapeInput
    from agentic_scraper.backend.config.types import OpenAIConfig
    from agentic_scraper.backend.scraper.models import (
        ScrapeRequest,
        WorkerPoolConfig,
    )
    from agentic_scraper.backend.scraper.schemas import ScrapedItem

    # Only for typing to avoid runtime circular import
    from agentic_scraper.backend.scraper.worker_pool import _WorkerContext


logger = logging.getLogger(__name__)


# ───────────────────────────
# Cancel helpers
# ───────────────────────────


def _safe_should_cancel(should_cancel: Callable[[], bool] | None) -> bool:
    """
    Safely evaluate a user-supplied cancel predicate.
    Any exception is logged at debug and treated as "not canceled".
    """
    if not should_cancel:
        return False
    try:
        return bool(should_cancel())
    except Exception as e:  # noqa: BLE001 - user predicate may raise arbitrary exceptions
        logger.debug("should_cancel predicate raised: %r", e)
        return False


def early_cancel_or_raise(cancel_event: asyncio.Event | None) -> None:
    """Raise CancelledError if the cancel_event is set (legacy signature)."""
    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError


def early_cancel_or_raise_ext(
    cancel_event: asyncio.Event | None,
    should_cancel: Callable[[], bool] | None = None,
) -> None:
    """
    Raise CancelledError if either the event is set or the predicate returns True.
    Separated from the legacy signature to avoid TRY301: no raise inside a try.
    """
    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError
    if _safe_should_cancel(should_cancel):
        raise asyncio.CancelledError


# ───────────────────────────
# Queue / request helpers
# ───────────────────────────


async def dequeue_next(
    queue: asyncio.Queue[ScrapeInput],
    *,
    worker_id: int,
) -> tuple[str, str]:
    """
    Get next (url, text) from the queue and log selection.

    Contract: if this function raises, it has NOT removed an item from the queue.
    """
    url, text = await queue.get()
    logger.debug(MSG_DEBUG_WORKER_PICKED_URL.format(worker_id=worker_id, url=url))
    return url, text


def build_request(
    *,
    scrape_input: ScrapeInput,
    take_screenshot: bool,
    openai: OpenAIConfig | None,
    worker_id: int,
    scrape_request_cls: type[ScrapeRequest],
) -> ScrapeRequest:
    """Construct ScrapeRequest with optional OpenAI credentials and log it."""
    url, text = scrape_input
    kwargs: dict[str, object] = {"text": text, "url": url, "take_screenshot": take_screenshot}
    if openai is not None:
        kwargs["openai"] = openai
    request = scrape_request_cls(**kwargs)
    logger.debug(MSG_DEBUG_WORKER_CREATED_REQUEST.format(worker_id=worker_id, url=url))
    return request


# ───────────────────────────
# Result / callback helpers
# ───────────────────────────


def handle_success_item(
    *,
    item: ScrapedItem | None,
    results: list[ScrapedItem],
    url: str,
    worker_id: int,
    context: _WorkerContext,
) -> None:
    """
    Append successful items, emit logs, and call on_item_processed if present.
    User callbacks are guarded so they never break the worker loop.
    """
    if context.settings.is_verbose_mode:
        logger.debug(MSG_DEBUG_WORKER_GOT_ITEM.format(worker_id=worker_id, item=item))
    if item is not None:
        results.append(item)
        logger.debug(MSG_DEBUG_WORKER_ITEM_APPENDED.format(worker_id=worker_id, url=url))
        if context.on_item_processed:
            try:
                context.on_item_processed(item)
            except Exception as error:  # noqa: BLE001 — user callback must never break the pool
                logger.warning(MSG_WARNING_ON_ITEM_PROCESSED_FAILED.format(error=error))
    else:
        logger.debug(MSG_DEBUG_WORKER_NO_ITEM.format(worker_id=worker_id, url=url))


def handle_failure(
    *,
    url: str,
    error: Exception,
    context: _WorkerContext,
) -> None:
    """Log failures consistently and call on_error if provided (callback is guarded)."""
    if context.settings.is_verbose_mode:
        logger.exception(MSG_ERROR_WORKER_FAILED.format(url=url))
    else:
        logger.warning(MSG_WARNING_WORKER_FAILED_SHORT.format(url=url, error=error))
    if context.on_error:
        try:
            context.on_error(url, error)
        except Exception as cb_error:  # noqa: BLE001 — user callback must never break the pool
            logger.warning(MSG_WARNING_ON_ERROR_CALLBACK_FAILED.format(error=cb_error))


def log_progress_verbose(
    *,
    worker_id: int,
    url: str,
    queue: asyncio.Queue[ScrapeInput],
    context: _WorkerContext,
) -> None:
    """Detailed progress logging guarded by verbose mode."""
    if context.settings.is_verbose_mode:
        logger.debug(
            MSG_DEBUG_WORKER_PROGRESS.format(
                worker_id=worker_id,
                url=url,
                remaining=queue.qsize(),
            )
        )


def call_progress_callback(
    *,
    context: _WorkerContext,
) -> None:
    """
    Best-effort progress computation (processed vs total) with an intentionally lock-free read.
    Workers increment processed_count under a lock; here we read once without awaiting.
    """
    on_progress: Callable[[int, int], None] | None = context.on_progress
    if not on_progress:
        return

    processed = max(getattr(context, "processed_count", 0), 0)
    try:
        on_progress(processed, context.total_inputs)
    except Exception as error:  # noqa: BLE001 — user callback must never break the pool
        logger.warning(MSG_WARNING_PROGRESS_CALLBACK_FAILED.format(error=error))


# ───────────────────────────
# Ordering helpers
# ───────────────────────────


async def _prepare_queue_and_ordering(
    inputs: list[ScrapeInput],
    config: WorkerPoolConfig,
) -> tuple[
    asyncio.Queue[ScrapeInput],
    list[ScrapedItem],
    list[ScrapedItem | None] | None,
    dict[str, deque[int]] | None,
]:
    """
    Initialize the queue with inputs and set up ordering structures if enabled.
    """
    queue: asyncio.Queue[ScrapeInput] = asyncio.Queue(maxsize=config.max_queue_size or 0)
    results: list[ScrapedItem] = []

    ordered_results: list[ScrapedItem | None] | None = None
    url_to_indices: dict[str, deque[int]] | None = None

    if config.preserve_order:
        ordered_results = [None] * len(inputs)
        url_to_indices = {}
        for idx, (url, _text) in enumerate(inputs):
            url_to_indices.setdefault(url, deque()).append(idx)

    for url, text in inputs:
        await queue.put((url, text))
        logger.debug(MSG_DEBUG_POOL_ENQUEUED_URL.format(url=url))

    return queue, results, ordered_results, url_to_indices


async def place_ordered_result(
    *,
    context: _WorkerContext,
    url: str,
    item: ScrapedItem | None,
) -> bool:
    """
    Place `item` into `context.ordered_results` in input order when enabled.

    Returns:
        True if the item was placed; False if ordering is disabled,
        structures are missing, no index is pending for the URL,
        or the target slot is already filled.
    """
    if (
        item is None
        or not context.preserve_order
        or context.ordered_results is None
        or context.url_to_indices is None
    ):
        return False

    async with context.order_lock:
        indices = context.url_to_indices.get(url)
        if not indices:
            return False

        # Prefer deque for O(1) pops from the left.
        if isinstance(indices, deque):
            idx = indices.popleft()
            if not indices:
                # Optional: keep the map tidy
                context.url_to_indices.pop(url, None)
        else:
            # Fallback for list[int]
            idx = indices.pop(0)
            if not indices:
                context.url_to_indices.pop(url, None)

        if 0 <= idx < len(context.ordered_results) and context.ordered_results[idx] is None:
            context.ordered_results[idx] = item
            return True

        return False


# ───────────────────────────
# Join / cancellation helpers
# ───────────────────────────


async def _poll_cancel_predicate(
    should_cancel: Callable[[], bool],
    interval_sec: float = 0.1,
) -> None:
    """Periodically poll a cancel predicate; return when it indicates cancel."""
    while True:
        if _safe_should_cancel(should_cancel):
            return
        await asyncio.sleep(interval_sec)


async def _await_join_with_optional_cancel(
    queue: asyncio.Queue[ScrapeInput],
    cancel_event: asyncio.Event | None,
    should_cancel: Callable[[], bool] | None = None,
) -> None:
    """
    Await queue.join(), with optional early cancellation (event and/or predicate).
    """
    if cancel_event is None and not should_cancel:
        await queue.join()
        return

    join_task: asyncio.Task[Any] = asyncio.create_task(queue.join(), name="queue-join")
    waiters: set[asyncio.Task[Any]] = {join_task}

    cancel_task: asyncio.Task[Any] | None = None
    if cancel_event is not None:
        cancel_task = asyncio.create_task(cancel_event.wait(), name="cancel-wait")
        waiters.add(cancel_task)

    poll_task: asyncio.Task[Any] | None = None
    if should_cancel is not None:
        poll_task = asyncio.create_task(_poll_cancel_predicate(should_cancel), name="cancel-poll")
        waiters.add(poll_task)

    done, _ = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)

    if join_task not in done:
        # Drain queue so join() can complete deterministically.
        while True:
            try:
                _ = queue.get_nowait()
            except asyncio.QueueEmpty:  # noqa: PERF203 - acceptable to avoid racing qsize()
                break
            else:
                queue.task_done()
        await join_task

    # Cleanup extra tasks
    for t in (cancel_task, poll_task):
        if t and not t.done():
            t.cancel()
    await asyncio.gather(*(t for t in (cancel_task, poll_task) if t), return_exceptions=True)
