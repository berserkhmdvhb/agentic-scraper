"""
Asynchronous worker pool for structured data extraction.

Responsibilities:
- Spawn and manage N async workers to process `(url, text)` scraping inputs.
- Build `ScrapeRequest` objects and delegate extraction to the active agent.
- Support cooperative cancellation (event and/or predicate).
- Optionally preserve input ordering in the final results.
- Surface progress via guarded callbacks and structured logging.

Public API:
- `run_worker_pool`: Orchestrate queueing, workers, and result collation.
- `worker`: Worker coroutine that processes items until the queue is drained.

Operational:
- Concurrency: Fully asyncio-based; one Task per worker, plus queue join/pollers.
- Ordering: Optional input-order preservation via pre-sized buffer + index map.
- Logging: Uses message constants; verbose mode includes tracebacks.
- Cancellation: Cooperative. Workers check before/after blocking and long work.

Usage:
    results = await run_worker_pool(
        inputs, settings=settings, config=pool_config,
        cancel_event=cancel_event, should_cancel=should_cancel,
    )

Notes:
- User callbacks (on_progress / on_item_processed / on_error) are guarded and
  must never break worker liveness.
- Per-item timeouts are supported via `settings.scrape_timeout_s` (if present).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_POOL_CANCELLING_WORKERS,
    MSG_DEBUG_POOL_DONE,
    MSG_DEBUG_POOL_SPAWNED_WORKERS,
    MSG_DEBUG_WORKER_CANCELLED,
    MSG_INFO_WORKER_POOL_START,
)
from agentic_scraper.backend.scraper import agents as agents_mode
from agentic_scraper.backend.scraper.models import (
    ScrapeRequest,
    WorkerPoolConfig,
)
from agentic_scraper.backend.scraper.worker_pool_helpers import (
    _await_join_with_optional_cancel,
    _prepare_queue_and_ordering,
    build_request,
    call_progress_callback,
    dequeue_next,
    handle_failure,
    handle_success_item,
    log_progress_verbose,
    place_ordered_result,
)
from agentic_scraper.backend.scraper.worker_pool_helpers import (
    early_cancel_or_raise_ext as early_cancel_or_raise,
)

if TYPE_CHECKING:
    from agentic_scraper.backend.config.aliases import (
        OnErrorCallback,
        OnSuccessCallback,
        ScrapeInput,
    )
    from agentic_scraper.backend.config.types import OpenAIConfig
    from agentic_scraper.backend.core.settings import Settings
    from agentic_scraper.backend.scraper.schemas import ScrapedItem


@dataclass
class _WorkerContext:
    """
    Runtime context shared by workers in the pool.

    Attributes:
        settings (Settings): Global runtime settings.
        take_screenshot (bool): Whether screenshots should be captured by agents.
        total_inputs (int): Total number of inputs enqueued (for progress).
        processed_count (int): Number of inputs the pool has processed so far.
        processed_lock (asyncio.Lock): Guards `processed_count` increments.
        openai (OpenAIConfig | None): Optional OpenAI credentials (LLM modes).
        on_item_processed (OnSuccessCallback | None): Success callback (guarded).
        on_error (OnErrorCallback | None): Error callback (guarded).
        on_progress (Callable[[int, int], None] | None): Progress callback (guarded).
        cancel_event (asyncio.Event | None): Event-style cancel signal.
        should_cancel (Callable[[], bool] | None): Predicate-style cancel signal.
        preserve_order (bool): If True, maintain input order in outputs.
        ordered_results (list[ScrapedItem | None] | None): Slot-buffered results.
        url_to_indices (dict[str, deque[int]] | None): URL → pending index slots.
        order_lock (asyncio.Lock): Serializes ordered placement.
    """

    settings: Settings
    take_screenshot: bool
    total_inputs: int
    processed_count: int = 0
    processed_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    openai: OpenAIConfig | None = None
    on_item_processed: OnSuccessCallback | None = None
    on_error: OnErrorCallback | None = None
    on_progress: Callable[[int, int], None] | None = None
    cancel_event: asyncio.Event | None = None
    should_cancel: Callable[[], bool] | None = None
    preserve_order: bool = False
    ordered_results: list[ScrapedItem | None] | None = None
    url_to_indices: dict[str, deque[int]] | None = None
    order_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


logger = logging.getLogger(__name__)


async def worker(
    *,
    worker_id: int,
    queue: asyncio.Queue[ScrapeInput],
    results: list[ScrapedItem],
    context: _WorkerContext,
) -> None:
    """
    Worker coroutine that consumes inputs and performs extraction.

    Args:
        worker_id (int): Identifier for logging/tracing.
        queue (asyncio.Queue[ScrapeInput]): Shared work queue of `(url, text)`.
        results (list[ScrapedItem]): Shared result buffer (unordered).
        context (_WorkerContext): Shared runtime context.

    Notes:
        - Completion order is non-deterministic unless `preserve_order` is True.
        - Cancellation is checked:
            (a) before blocking on the queue,
            (b) after dequeue (so task_done still runs in `finally`),
            (c) immediately after extraction.
        - Per-item timeout is honored when `settings.scrape_timeout_s` is set.
    """
    try:
        while True:
            # Early cancel before blocking, so workers can exit promptly.
            early_cancel_or_raise(context.cancel_event, context.should_cancel)

            # Blocking dequeue — if this raises, we didn't remove anything.
            url, text = await dequeue_next(queue, worker_id=worker_id)

            try:
                # Check again *after* dequeue; still ensure task_done() will run in finally.
                early_cancel_or_raise(context.cancel_event, context.should_cancel)

                # Compose request (OpenAI creds injected only when present).
                request = build_request(
                    scrape_input=(url, text),
                    take_screenshot=context.take_screenshot,
                    openai=context.openai,
                    worker_id=worker_id,
                    scrape_request_cls=ScrapeRequest,
                )

                # Optional per-item timeout (if configured on settings).
                timeout_s = getattr(context.settings, "scrape_timeout_s", None)
                if isinstance(timeout_s, (int, float)) and timeout_s > 0:
                    item = await asyncio.wait_for(
                        agents_mode.extract_structured_data(request, settings=context.settings),
                        timeout=timeout_s,
                    )
                else:
                    item = await agents_mode.extract_structured_data(
                        request, settings=context.settings
                    )

                # Bail quickly if cancel was signaled during extraction.
                early_cancel_or_raise(context.cancel_event, context.should_cancel)

                # Successful extraction → append + guarded callbacks.
                handle_success_item(
                    item=item,
                    results=results,
                    url=url,
                    worker_id=worker_id,
                    context=context,
                )

                # If ordering is enabled, place into the pre-sized buffer.
                await place_ordered_result(context=context, url=url, item=item)

            except (AssertionError, AttributeError, TypeError) as e:
                # Likely programmer/internal errors. Log + re-raise in verbose mode
                # so they don't masquerade as routine scrape failures during debugging.
                handle_failure(url=url, error=e, context=context)
                if context.settings.is_verbose_mode:
                    raise
            except Exception as e:  # noqa: BLE001 — routine failure path (network/agent/etc.)
                handle_failure(url=url, error=e, context=context)
            finally:
                # Always acknowledge the queue item to make `queue.join()` progress.
                with suppress(ValueError):
                    # ValueError only if task_done() is called too many times.
                    queue.task_done()

                # Update processed counter (coarse-grained lock, cheap in asyncio).
                async with context.processed_lock:
                    context.processed_count += 1

                # Verbose progress log and guarded progress callback.
                log_progress_verbose(worker_id=worker_id, url=url, queue=queue, context=context)
                call_progress_callback(context=context)

    except asyncio.CancelledError:
        # Normal shutdown path when the pool controller cancels the worker task.
        logger.debug(MSG_DEBUG_WORKER_CANCELLED.format(worker_id=worker_id))


async def run_worker_pool(
    inputs: list[ScrapeInput],
    *,
    settings: Settings,
    config: WorkerPoolConfig,
    cancel_event: asyncio.Event | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> list[ScrapedItem]:
    """
    Launch and manage a pool of workers to process scraping inputs concurrently.

    Args:
        inputs (list[ScrapeInput]): Prepared `(url, text)` inputs to process.
        settings (Settings): Global runtime settings object.
        config (WorkerPoolConfig): Pool config (concurrency, callbacks, etc.).
        cancel_event (asyncio.Event | None): Event-style cancel signal.
        should_cancel (Callable[[], bool] | None): Predicate-style cancel signal.

    Returns:
        list[ScrapedItem]: Extracted items; input order if `preserve_order=True`.

    Notes:
        - Spawns `min(concurrency, len(inputs))` workers to avoid idle tasks.
        - Initial and final progress callbacks (0/total and total/total) are emitted
          unless cancellation is already signaled.
        - When `preserve_order` is on, results are compacted from the slot buffer.
    """
    start_t = time.perf_counter()
    total = len(inputs)

    # Respect a should_cancel provided at config-level first, then fallback.
    composed_should_cancel = config.should_cancel or should_cancel

    # Early return when there's nothing to process (still emit a benign progress).
    if total == 0:
        cb = config.on_progress
        event_canceled = cancel_event and cancel_event.is_set()
        manual_canceled = composed_should_cancel and composed_should_cancel()
        if cb is not None and not event_canceled and not manual_canceled:
            with suppress(Exception):
                cb(0, 0)
        return []

    # Emit initial progress (0 of total) unless already canceled.
    cb = config.on_progress
    event_canceled = cancel_event and cancel_event.is_set()
    manual_canceled = composed_should_cancel and composed_should_cancel()
    if cb is not None and not event_canceled and not manual_canceled:
        with suppress(Exception):
            cb(0, total)

    # Prepare queue, shared result buffers, and optional ordering structures.
    (
        queue,
        results,
        ordered_results,
        url_to_indices,
    ) = await _prepare_queue_and_ordering(inputs, config)

    if settings.is_verbose_mode:
        logger.info(MSG_INFO_WORKER_POOL_START.format(enabled=config.take_screenshot))

    # Cap the number of workers to available work (at least one).
    worker_count = min(config.concurrency, max(1, total))

    # Shared context consumed by workers.
    context = _WorkerContext(
        settings=settings,
        take_screenshot=config.take_screenshot,
        total_inputs=total,
        openai=config.openai,
        on_item_processed=config.on_item_processed,
        on_error=config.on_error,
        on_progress=config.on_progress,
        cancel_event=cancel_event,
        should_cancel=composed_should_cancel,
        preserve_order=config.preserve_order,
        ordered_results=ordered_results,
        url_to_indices=url_to_indices,
    )

    # Spawn `worker_count` independent tasks. Each task runs until `queue.join()`.
    workers = [
        asyncio.create_task(
            worker(
                worker_id=i,
                queue=queue,
                results=results,
                context=context,
            ),
            name=f"worker-{i}",
        )
        for i in range(worker_count)
    ]
    logger.debug(MSG_DEBUG_POOL_SPAWNED_WORKERS.format(count=len(workers)))

    try:
        # Wait for the queue to drain, but allow early exit on cancel signals.
        await _await_join_with_optional_cancel(queue, cancel_event, composed_should_cancel)
    finally:
        # Cancel the workers deterministically and wait them out.
        logger.debug(MSG_DEBUG_POOL_CANCELLING_WORKERS)
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    # Emit final progress (total/total) unless we were canceled.
    cb = config.on_progress
    event_canceled = cancel_event and cancel_event.is_set()
    manual_canceled = composed_should_cancel and composed_should_cancel()
    if cb is not None and not event_canceled and not manual_canceled:
        with suppress(Exception):
            cb(total, total)

    elapsed = time.perf_counter() - start_t

    # If we preserved order, compact from the slot buffer (skip missing slots).
    if config.preserve_order and context.ordered_results is not None:
        final_results = [it for it in context.ordered_results if it is not None]
        logger.debug(MSG_DEBUG_POOL_DONE.format(count=len(final_results), time=elapsed))
        return final_results

    # Otherwise, return completion-order results (already appended as items arrived).
    logger.debug(MSG_DEBUG_POOL_DONE.format(count=len(results), time=elapsed))
    return results
