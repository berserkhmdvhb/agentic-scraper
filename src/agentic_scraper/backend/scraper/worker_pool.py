"""
Asynchronous worker pool for structured data extraction.

This module runs a configurable number of worker coroutines to process
scraping tasks concurrently. Each worker extracts structured data from
preprocessed input using either LLM-based or rule-based agents.

The core pipeline:
1. Inputs (ScrapeInput) are enqueued.
2. Workers consume and process them concurrently.
3. Each item is parsed and appended to results (completion order by default).
4. Optional callbacks can be used for progress/error tracking.

Used by the scraping pipeline to scale up parallel scraping.
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

from agentic_scraper.backend.api.stores import job_store
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_POOL_CANCELLING_WORKERS,
    MSG_DEBUG_POOL_DONE,
    MSG_DEBUG_POOL_SPAWNED_WORKERS,
    MSG_DEBUG_WORKER_CANCELLED,
    MSG_INFO_WORKER_POOL_START,
)
from agentic_scraper.backend.config.types import JobStatus
from agentic_scraper.backend.scraper.agents import extract_structured_data
from agentic_scraper.backend.scraper.models import (
    ScrapeRequest,
    WorkerPoolConfig,
)
from agentic_scraper.backend.scraper.worker_pool_helpers import (
    _await_join_with_optional_cancel,
    _prepare_queue_and_ordering,
    build_request,
    call_progress_callback,
    composite_should_cancel_factory,
    dequeue_next,
    emit_initial_progress,
    finalize_progress,
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
    """Internal runtime context shared by each worker instance."""

    settings: Settings
    take_screenshot: bool
    total_inputs: int
    processed_count: int = 0
    processed_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    job_id: str | None = None
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


@dataclass
class _RuntimeOpts:
    """Runtime-only options (kept separate to reduce function arg count)."""

    cancel_event: asyncio.Event | None = None
    should_cancel: Callable[[], bool] | None = None
    job_id: str | None = None


logger = logging.getLogger(__name__)


async def worker(
    *,
    worker_id: int,
    queue: asyncio.Queue[ScrapeInput],
    results: list[ScrapedItem],
    context: _WorkerContext,
) -> None:
    """
    Worker coroutine that consumes ScrapeInput items and performs extraction.

    Note:
        - Result order is completion-order by default (non-deterministic).
        - If `context.preserve_order` is True, results are also placed into
          `context.ordered_results` according to the first-come index map.
    """
    try:
        while True:
            # Early cancel before blocking on the queue.
            early_cancel_or_raise(context.cancel_event, context.should_cancel)

            url, text = await dequeue_next(queue, worker_id=worker_id)

            try:
                # Check cancellation again immediately after we dequeue, but keep it inside
                # the try/finally so task_done() will always be called.
                early_cancel_or_raise(context.cancel_event, context.should_cancel)

                request = build_request(
                    scrape_input=(url, text),
                    take_screenshot=context.take_screenshot,
                    openai=context.openai,
                    worker_id=worker_id,
                    scrape_request_cls=ScrapeRequest,
                )

                # Per-item timeout if configured on settings (in seconds).
                timeout_s = getattr(context.settings, "scrape_timeout_s", None)
                if isinstance(timeout_s, (int, float)) and timeout_s > 0:
                    item = await asyncio.wait_for(
                        extract_structured_data(request, settings=context.settings),
                        timeout=timeout_s,
                    )
                else:
                    item = await extract_structured_data(request, settings=context.settings)

                # Bail quickly if cancellation was signaled during extraction
                early_cancel_or_raise(context.cancel_event, context.should_cancel)

                # Success handling + callbacks
                handle_success_item(
                    item=item,
                    results=results,
                    url=url,
                    worker_id=worker_id,
                    context=context,
                )

                # Optional: place into ordered results (extracted helper reduces branching).
                await place_ordered_result(context=context, url=url, item=item)

            except (AssertionError, AttributeError, TypeError) as e:
                # Likely programming/internal errors. Log and re-raise in verbose mode
                # so they don't masquerade as routine scrape failures during debugging.
                handle_failure(url=url, error=e, context=context)
                if context.settings.is_verbose_mode:
                    raise
            except Exception as e:  # noqa: BLE001 - log failure then continue
                handle_failure(url=url, error=e, context=context)
            finally:
                # 1) Acknowledge the task first to avoid join deadlocks.
                with suppress(ValueError):
                    # Only ValueError is expected here (too many task_done calls).
                    queue.task_done()

                # 2) Update processed counter (atomic-ish via lock in asyncio context).
                async with context.processed_lock:
                    context.processed_count += 1
                    # Emit fractional progress to job store.
                    if context.job_id:
                        total = max(1, context.total_inputs)
                        prog = min(1.0, max(0.0, context.processed_count / total))
                        job_store.update_job(context.job_id, progress=prog)

                # 3) Verbose progress log (safe to call directly).
                log_progress_verbose(
                    worker_id=worker_id,
                    url=url,
                    queue=queue,
                    context=context,
                )

                # 4) Progress callback is internally guarded in the helper.
                call_progress_callback(context=context)

    except asyncio.CancelledError:
        logger.debug(MSG_DEBUG_WORKER_CANCELLED.format(worker_id=worker_id))


async def run_worker_pool(
    inputs: list[ScrapeInput],
    *,
    settings: Settings,
    config: WorkerPoolConfig,
    runtime: _RuntimeOpts | None = None,
) -> list[ScrapedItem]:
    """
    Launch and manage a pool of workers to process scraping inputs concurrently.
    """
    if runtime is None:
        runtime = _RuntimeOpts()

    start_t = time.perf_counter()
    total = len(inputs)

    # Early exit: nothing to do
    if total == 0:
        emit_initial_progress(
            total=0,
            on_progress=config.on_progress,
            cancel_event=runtime.cancel_event,
            should_cancel=config.should_cancel,
        )
        return []

    # Initial progress for UIs (0 / total). Do not force 100% when canceled.
    emit_initial_progress(
        total=total,
        on_progress=config.on_progress,
        cancel_event=runtime.cancel_event,
        should_cancel=config.should_cancel,
    )

    # Mark job as RUNNING at pool start (best-effort).
    if runtime.job_id:
        with suppress(Exception):
            job_store.update_job(runtime.job_id, status=JobStatus.RUNNING, progress=0.0)

    # Prepare queue, results, and ordering structures
    (
        queue,
        results,
        ordered_results,
        url_to_indices,
    ) = await _prepare_queue_and_ordering(inputs, config)

    if settings.is_verbose_mode:
        logger.info(MSG_INFO_WORKER_POOL_START.format(enabled=config.take_screenshot))

    # Cap worker count to available work (at least 1)
    worker_count = min(config.concurrency, max(1, total))

    # Compose a cancel check that respects job-store CANCELED and external signals
    composed_should_cancel = composite_should_cancel_factory(
        should_cancel=config.should_cancel,
        job_id=runtime.job_id,
    )

    context = _WorkerContext(
        settings=settings,
        take_screenshot=config.take_screenshot,
        total_inputs=total,
        job_id=runtime.job_id,
        openai=config.openai,
        on_item_processed=config.on_item_processed,
        on_error=config.on_error,
        on_progress=config.on_progress,
        cancel_event=runtime.cancel_event,
        should_cancel=composed_should_cancel,
        preserve_order=config.preserve_order,
        ordered_results=ordered_results,
        url_to_indices=url_to_indices,
    )

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
        await _await_join_with_optional_cancel(
            queue,
            runtime.cancel_event,
            should_cancel=composed_should_cancel,
        )
    finally:
        logger.debug(MSG_DEBUG_POOL_CANCELLING_WORKERS)
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    finalize_progress(
        total=total,
        on_progress=config.on_progress,
        cancel_event=runtime.cancel_event,
        should_cancel=config.should_cancel,
    )

    elapsed = time.perf_counter() - start_t
    if config.preserve_order and context.ordered_results is not None:
        final_results = [it for it in context.ordered_results if it is not None]
        logger.debug(MSG_DEBUG_POOL_DONE.format(count=len(final_results), time=elapsed))
        return final_results

    logger.debug(MSG_DEBUG_POOL_DONE.format(count=len(results), time=elapsed))
    return results
