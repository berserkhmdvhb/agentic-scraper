"""
Helper utilities for the asynchronous scraping worker pool.

Responsibilities:
- Encapsulate cancellation checks and early-exit guards.
- Build queue/request structures and manage optional output ordering.
- Invoke user callbacks safely (never let them break the pool).
- Provide progress reporting and robust error logging helpers.

Public API:
- `dequeue_next`: Pop next input for a worker and log selection.
- `build_request`: Construct a `ScrapeRequest` with optional OpenAI config.
- `handle_success_item`: Append/emit a produced item and guard callbacks.
- `handle_failure`: Uniform failure logging + guarded `on_error`.
- `log_progress_verbose`: Verbose-only progress logging.
- `call_progress_callback`: Guarded `on_progress` invocation.
- `_prepare_queue_and_ordering`: Initialize queue and optional ordering buffers.
- `place_ordered_result`: Place an item respecting input-order semantics.
- `_await_join_with_optional_cancel`: Join queue with optional cancel support.

Operational:
- Concurrency: Functions are designed for use inside multiple async workers.
- Logging: Uses message constants; verbose mode controls stack traces.
- Idempotency: Ordering helpers avoid double-inserting results.

Usage:
    from agentic_scraper.backend.scraper.worker_pool_helpers import build_request, dequeue_next

    url, text = await dequeue_next(queue, worker_id=1)
    req = build_request(
        scrape_input=(url, text),
        take_screenshot=True,
        openai=openai_cfg,
        worker_id=1,
        scrape_request_cls=ScrapeRequest,
    )

Notes:
- Callbacks from user code are wrapped in try/except and logged on failure to
  preserve pool liveness.
- Ordering is optional and enabled via `WorkerPoolConfig.preserve_order`.
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
from agentic_scraper.backend.scraper.cancel_helpers import (
    CancelToken,
)
from agentic_scraper.backend.scraper.cancel_helpers import (
    is_canceled as _is_canceled,
)
from agentic_scraper.backend.scraper.cancel_helpers import (
    safe_should_cancel as _safe_pred,
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

    Args:
        should_cancel (Callable[[], bool] | None): User predicate that indicates cancellation.

    Returns:
        bool: True if predicate returns truthy; False on None or predicate error.

    Notes:
        - Delegates to shared `_safe_pred` to keep logging/behavior consistent project-wide.
    """
    return _safe_pred(should_cancel)


def early_cancel_or_raise(cancel_event: asyncio.Event | None) -> None:
    """
    Raise `asyncio.CancelledError` if the event is already set.

    Args:
        cancel_event (asyncio.Event | None): Event-style cancel signal.

    Raises:
        asyncio.CancelledError: When the event indicates cancellation.

    Notes:
        - Kept for legacy call sites that only use an event (no predicate).
    """
    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError


def early_cancel_or_raise_ext(
    cancel_event: asyncio.Event | None,
    should_cancel: Callable[[], bool] | None = None,
) -> None:
    """
    Raise `asyncio.CancelledError` if either event or predicate indicates cancel.

    Args:
        cancel_event (asyncio.Event | None): Event-style cancel signal.
        should_cancel (Callable[[], bool] | None): Predicate-style cancel signal.

    Raises:
        asyncio.CancelledError: When either signal indicates cancellation.

    Notes:
        - We unify both mechanisms by constructing a `CancelToken` and reusing the
          shared `is_canceled` check to keep semantics identical to the rest of the codebase.
    """
    token = CancelToken(event=cancel_event, should_cancel=should_cancel)
    if _is_canceled(token):
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
    Dequeue the next `(url, text)` for a worker and log the selection.

    Args:
        queue (asyncio.Queue[ScrapeInput]): Shared input queue.
        worker_id (int): Worker identifier for logging.

    Returns:
        tuple[str, str]: The `(url, text)` pair.

    Notes:
        - Contract: if this function raises before completion, it must not have
          removed an item from the queue. Using `await queue.get()` ensures atomicity.
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
    """
    Construct a `ScrapeRequest` from input and optional OpenAI credentials.

    Args:
        scrape_input (ScrapeInput): Tuple `(url, text)` prepared by the pipeline.
        take_screenshot (bool): Whether screenshotting is enabled for this run.
        openai (OpenAIConfig | None): Optional OpenAI config for LLM agents.
        worker_id (int): Worker identifier, for logging only.
        scrape_request_cls (type[ScrapeRequest]): Request model class to instantiate.

    Returns:
        ScrapeRequest: A validated request object ready for agent processing.

    Notes:
        - We pass only supported kwargs; Pydantic validation handles coercion and errors.
        - OpenAI config is included conditionally to avoid leaking credentials to non-LLM runs.
    """
    url, text = scrape_input
    # Keep kwargs explicit; avoids accidental passing of unsupported fields.
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
    Append a produced item (if any), log details, and call the guarded callback.

    Args:
        item (ScrapedItem | None): The produced item or None.
        results (list[ScrapedItem]): Shared result buffer.
        url (str): URL for logging.
        worker_id (int): Worker identifier for logging.
        context (_WorkerContext): Worker context (holds settings and callbacks).

    Notes:
        - User callbacks are wrapped in try/except to protect worker liveness.
        - We log more verbosely only when `settings.is_verbose_mode` is enabled.
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
    """
    Log worker failure uniformly and invoke a guarded `on_error` callback if present.

    Args:
        url (str): The input URL associated with the failure.
        error (Exception): The exception raised by the worker.
        context (_WorkerContext): Worker context with logging/callbacks.

    Notes:
        - Verbose mode logs the full traceback; otherwise a short message is logged.
        - The `on_error` callback is wrapped to avoid breaking the pool.
    """
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
    """
    Emit detailed progress logs when in verbose mode.

    Args:
        worker_id (int): Worker identifier for logging.
        url (str): URL being processed.
        queue (asyncio.Queue[ScrapeInput]): Work queue (used to report remaining size).
        context (_WorkerContext): Worker context for verbosity flag.
    """
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
    Compute and emit progress via a guarded callback.

    Notes:
        - Intentionally performs a lock-free read of `processed_count` to avoid
          contention among workers. Minor skew in the reported number is acceptable.
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
    Initialize the input queue and optional ordering data structures.

    Args:
        inputs (list[ScrapeInput]): Prepared `(url, text)` inputs.
        config (WorkerPoolConfig): Pool configuration (preserve_order, max_queue_size, ...).

    Returns:
        tuple[queue, results, ordered_results, url_to_indices]:
            - queue: Work queue seeded with all inputs (bounded if configured).
            - results: Shared results list (used when ordering is disabled).
            - ordered_results: Fixed-size list with per-input slots (or None).
            - url_to_indices: Map URL → deque of pending indices (or None).

    Notes:
        - We use a `deque[int]` for O(1) pops from the left when placing results by URL.
        - When `preserve_order` is False, `ordered_results` and `url_to_indices` are None.
    """
    # Build a bounded queue only if max_queue_size is set; 0 means unbounded (Queue default).
    queue: asyncio.Queue[ScrapeInput] = asyncio.Queue(maxsize=config.max_queue_size or 0)
    results: list[ScrapedItem] = []

    ordered_results: list[ScrapedItem | None] | None = None
    url_to_indices: dict[str, deque[int]] | None = None

    if config.preserve_order:
        # Pre-allocate the result slots for deterministic placement by original input order.
        ordered_results = [None] * len(inputs)
        url_to_indices = {}
        for idx, (url, _text) in enumerate(inputs):
            url_to_indices.setdefault(url, deque()).append(idx)

    # Seed the queue (one put per input). We log enqueueing for traceability in verbose/debug flows.
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
    Place `item` into `context.ordered_results` following original input order.

    Args:
        context (_WorkerContext): Worker context holding ordering buffers/locks.
        url (str): URL whose next slot should be filled.
        item (ScrapedItem | None): The item to place (ignored when None).

    Returns:
        bool: True if placed into an ordered slot; False otherwise.

    Notes:
        - If ordering is disabled, or no slot is pending for the URL, the function
          returns False so callers may append to unordered results instead.
    """
    if (
        item is None
        or not context.preserve_order
        or context.ordered_results is None
        or context.url_to_indices is None
    ):
        return False

    # Serialize placement to avoid two workers racing on the same URL slot.
    async with context.order_lock:
        indices = context.url_to_indices.get(url)
        if not indices:
            return False

        # Prefer deque for O(1) pops; fall back to list for defensive compatibility.
        if isinstance(indices, deque):
            idx = indices.popleft()
            if not indices:
                # Keep the map tidy once the last index for a URL is consumed.
                context.url_to_indices.pop(url, None)
        else:
            idx = indices.pop(0)
            if not indices:
                context.url_to_indices.pop(url, None)

        # Guard against corrupted indices and double-writes.
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
    """
    Poll a predicate until it signals cancellation.

    Args:
        should_cancel (Callable[[], bool]): Predicate to poll.
        interval_sec (float): Sleep interval between polls.

    Notes:
        - Using a small sleep avoids a tight loop and yields control to the event loop.
    """
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
    Await `queue.join()`, with optional early cancellation (event and/or predicate).

    Args:
        queue (asyncio.Queue[ScrapeInput]): Queue whose tasks are being processed.
        cancel_event (asyncio.Event | None): Event-based cancel signal.
        should_cancel (Callable[[], bool] | None): Predicate-based cancel signal.

    Notes:
        - If a cancel signal arrives before `join()` completes, we drain the queue by
          repeatedly calling `get_nowait()`/`task_done()` so `queue.join()` can resolve.
          This avoids deadlocks where workers stop pulling but join still waits.
        - We ensure any auxiliary tasks (cancel-wait/poll) are cancelled and awaited to
          prevent task leaks.
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

    # Wait for either `join()` to complete or a cancel signal to arrive.
    done, _ = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)

    if join_task not in done:
        # A cancel path finished first: drain outstanding items so `join()` can finish.
        while True:
            try:
                _ = queue.get_nowait()
            except asyncio.QueueEmpty:  # noqa: PERF203 - acceptable; avoids racing qsize()
                break
            else:
                queue.task_done()
        await join_task

    # Cleanup any still-pending waiters to avoid lingering tasks.
    for t in (cancel_task, poll_task):
        if t and not t.done():
            t.cancel()
    await asyncio.gather(*(t for t in (cancel_task, poll_task) if t), return_exceptions=True)
