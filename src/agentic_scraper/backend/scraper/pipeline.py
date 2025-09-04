"""
Scraping pipeline orchestrator for AgenticScraper.

Responsibilities:
- Coordinate the end-to-end scraping flow: fetch → parse → extract via workers.
- Provide cancellation-aware execution and optional metrics gathering.

Public API:
- `scrape_urls`: Run the pipeline and return extracted items.
- `scrape_with_stats`: Run the pipeline and also return timing/count stats.
- `PipelineOptions`: Optional knobs for cancellation and job hook integrations.

Operational:
- Concurrency: Fetch and worker phases are concurrent; actual limits come from `Settings`.
- Retries: HTTP fetch retries are handled in the fetcher; worker retries depend on agent logic.
- Logging: Debug/Info logs summarize phase starts/finishes; verbose mode adds more detail.

Usage:
    from agentic_scraper.backend.scraper.pipeline import scrape_with_stats

    items, stats = await scrape_with_stats(
        urls=["https://example.com"],
        settings=settings,
        openai=openai_cfg,
    )

Notes:
- Inputs that fail to fetch are filtered out using `FETCH_ERROR_PREFIX` (caller receives only
  successfully-fetched pages).
- Cancellation is cooperative via `PipelineOptions(cancel_event/should_cancel)`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from agentic_scraper.backend.config.constants import FETCH_ERROR_PREFIX
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_PIPELINE_FETCH_START,
    MSG_DEBUG_PIPELINE_WORKER_POOL_START,
    MSG_DEBUG_SCRAPE_STATS_START,
    MSG_INFO_FETCH_COMPLETE,
    MSG_INFO_SCRAPE_STATS_COMPLETE,
    MSG_INFO_VALID_SCRAPE_INPUTS,
)
from agentic_scraper.backend.config.types import AgentMode, OpenAIConfig
from agentic_scraper.backend.scraper.cancel_helpers import CancelToken
from agentic_scraper.backend.scraper.fetcher import fetch_all
from agentic_scraper.backend.scraper.models import WorkerPoolConfig
from agentic_scraper.backend.scraper.parser import extract_main_text
from agentic_scraper.backend.scraper.worker_pool import run_worker_pool

if TYPE_CHECKING:
    from agentic_scraper.backend.config.aliases import ScrapeInput
    from agentic_scraper.backend.core.settings import Settings
    from agentic_scraper.backend.scraper.schemas import ScrapedItem


logger = logging.getLogger(__name__)


@dataclass
class PipelineOptions:
    """
    Optional controls and hooks for pipeline execution.

    Attributes:
        cancel_event (asyncio.Event | None): Event-driven cancel signal checked between phases.
        should_cancel (Callable[[], bool] | None): Predicate-based cancel signal for custom logic.
        job_hooks (object | None): Object with optional callbacks:
            - on_started(total: int) -> None
            - on_progress(done: int, total: int) -> None
            - on_item_processed(item: object) -> None
            - on_error(url: str, exc: Exception) -> None
            - on_failed(exc: Exception) -> None
            - on_completed(success: int, failed: int, duration_sec: float) -> None

    Notes:
        - Hooks are invoked best-effort and wrapped in `contextlib.suppress` to avoid surfacing
          user hook errors into the pipeline.
    """

    cancel_event: asyncio.Event | None = None
    should_cancel: Callable[[], bool] | None = None
    job_hooks: object | None = None


async def scrape_urls(
    urls: list[str],
    settings: Settings,
    openai: OpenAIConfig | None = None,
    *,
    options: PipelineOptions | None = None,
) -> list[ScrapedItem]:
    """
    Run the scraping pipeline on the given URLs and return extracted items.

    Flow:
        1) Cancellation pre-check (fast exit before any I/O).
        2) Fetch HTML concurrently (`fetch_all`), honoring cancellation.
        3) Extract main text for successfully fetched pages.
        4) Run worker pool (LLM or rule-based) to produce `ScrapedItem`s.

    Args:
        urls (list[str]): Target URLs (validated earlier in the request layer).
        settings (Settings): Runtime configuration (concurrency, agent_mode, etc.).
        openai (OpenAIConfig | None): Optional OpenAI credentials for LLM modes.
        options (PipelineOptions | None): Cancellation & job-hook options.

    Returns:
        list[ScrapedItem]: Extracted items (one or more per input, depending on agent).

    Raises:
        Exception: Propagated from worker pool if not handled internally.
                   (Fetch errors are captured as data and filtered out.)
    Examples:
        >>> items = await scrape_urls(["https://example.com"], settings)
        >>> len(items) >= 0
        True

    Notes:
        - Inputs that yield fetch errors (denoted by `FETCH_ERROR_PREFIX`) are skipped.
        - `openai` is passed only when `settings.agent_mode` is an LLM mode.
        - Order of outputs may differ from inputs when `preserve_order=False`.
    """
    # Back-compat: allow legacy keyword args (cancel_event, should_cancel, job_hooks)
    if options is None:
        options = PipelineOptions()
    cancel_event = options.cancel_event
    should_cancel = options.should_cancel
    job_hooks = options.job_hooks

    # Early cancel gate: do not start fetches if already canceled.
    if (cancel_event and cancel_event.is_set()) or (should_cancel and should_cancel()):
        if job_hooks and hasattr(job_hooks, "on_failed"):
            with contextlib.suppress(Exception):
                job_hooks.on_failed(RuntimeError("Scrape canceled before start."))
        return []

    logger.debug(MSG_DEBUG_PIPELINE_FETCH_START.format(count=len(urls)))

    # Fetch phase (concurrency governed by settings.fetch_concurrency).
    html_by_url = await fetch_all(
        urls=urls,
        settings=settings,
        concurrency=settings.fetch_concurrency,
        cancel=CancelToken(event=cancel_event, should_cancel=should_cancel),
    )

    logger.info(MSG_INFO_FETCH_COMPLETE.format(count=len(html_by_url)))

    # Transform successfully fetched pages into (url, main_text) inputs for the worker pool.
    # Non-obvious: we filter by prefix rather than exceptions because fetch errors are recorded
    # as strings to keep the pool resilient and return partial results.
    scrape_inputs: list[ScrapeInput] = [
        (url, extract_main_text(html))
        for url, html in html_by_url.items()
        if not html.startswith(FETCH_ERROR_PREFIX)
    ]

    num_skipped = len(urls) - len(scrape_inputs)
    logger.info(MSG_INFO_VALID_SCRAPE_INPUTS.format(valid=len(scrape_inputs), skipped=num_skipped))

    if job_hooks and hasattr(job_hooks, "on_started"):
        with contextlib.suppress(Exception):
            job_hooks.on_started(len(scrape_inputs))

    # Early exit if no valid inputs remain.
    if not scrape_inputs:
        if job_hooks and hasattr(job_hooks, "on_completed"):
            with contextlib.suppress(Exception):
                job_hooks.on_completed(success=0, failed=len(urls), duration_sec=0.0)
        return []

    # Re-check cancellation before spinning up the worker pool (cancels promptly after fetch).
    if (cancel_event and cancel_event.is_set()) or (should_cancel and should_cancel()):
        if job_hooks and hasattr(job_hooks, "on_failed"):
            with contextlib.suppress(Exception):
                job_hooks.on_failed(RuntimeError("Scrape canceled before worker pool start."))
        return []

    # Decide whether to wire OpenAI based on agent mode; avoids passing creds when unused.
    is_llm_mode = settings.agent_mode in {
        AgentMode.LLM_FIXED,
        AgentMode.LLM_DYNAMIC,
        AgentMode.LLM_DYNAMIC_ADAPTIVE,
    }

    # Construct pool configuration (note: some fields are optionally present on Settings).
    pool_config = WorkerPoolConfig(
        take_screenshot=settings.screenshot_enabled,
        openai=openai if is_llm_mode else None,
        concurrency=settings.llm_concurrency if is_llm_mode else settings.fetch_concurrency,
        on_progress=getattr(job_hooks, "on_progress", None),
        on_item_processed=getattr(job_hooks, "on_item_processed", None),
        on_error=getattr(job_hooks, "on_error", None),
        preserve_order=getattr(settings, "preserve_order", False),
        max_queue_size=getattr(settings, "max_queue_size", None),
        should_cancel=should_cancel,
    )

    logger.debug(
        MSG_DEBUG_PIPELINE_WORKER_POOL_START.format(count=len(scrape_inputs), is_llm=is_llm_mode)
    )

    # Delegate to worker pool: this may run CPU/LLM bound tasks under its own concurrency.
    return await run_worker_pool(
        inputs=scrape_inputs,
        settings=settings,
        config=pool_config,
        cancel_event=cancel_event,
        should_cancel=should_cancel,
    )


async def scrape_with_stats(
    urls: list[str],
    settings: Settings,
    openai: OpenAIConfig | None = None,
    *,
    options: PipelineOptions | None = None,
) -> tuple[list[ScrapedItem], dict[str, float | int]]:
    """
    Run the scraping pipeline and return both results and execution stats.

    This is a thin wrapper over `scrape_urls` that measures duration and
    summarizes counts (success/failed) for telemetry and API responses.

    Args:
        urls (list[str]): Target URLs.
        settings (Settings): Runtime configuration.
        openai (OpenAIConfig | None): Optional OpenAI credentials for LLM modes.
        options (PipelineOptions | None): Cancellation & job-hook options.

    Returns:
        tuple[list[ScrapedItem], dict[str, float | int]]:
            - items: Extracted items returned by `scrape_urls`.
            - stats: A dict with keys:
                * num_urls (int)
                * num_success (int)
                * num_failed (int)
                * duration_sec (float)
                * was_canceled (bool)

    Raises:
        Exception: Re-raises exceptions from `scrape_urls` after invoking `on_failed` hook.

    Examples:
        >>> items, stats = await scrape_with_stats(["https://example.com"], settings)
        >>> stats["num_urls"] == 1
        True

    Notes:
        - Cancellation is reflected in `stats["was_canceled"]` and reported via hooks.
    """
    # Back-compat for legacy kwargs
    if options is None:
        options = PipelineOptions()

    cancel_event = options.cancel_event
    should_cancel = options.should_cancel
    job_hooks = options.job_hooks

    logger.debug(
        MSG_DEBUG_SCRAPE_STATS_START.format(
            agent_mode=settings.agent_mode, has_openai=openai is not None
        )
    )

    start = time.perf_counter()

    try:
        results = await scrape_urls(
            urls,
            settings=settings,
            openai=openai,
            options=options,
        )
    except Exception as e:
        # Ensure failure is surfaced to hooks; never suppress.
        if job_hooks and hasattr(job_hooks, "on_failed"):
            with contextlib.suppress(Exception):
                job_hooks.on_failed(e)
        raise

    duration = round(time.perf_counter() - start, 2)

    logger.info(
        MSG_INFO_SCRAPE_STATS_COMPLETE.format(
            total=len(urls),
            success=len(results),
            failed=len(urls) - len(results),
            duration=duration,
        )
    )

    # Combine both cancel mechanisms to set a single flag for callers.
    event_canceled = cancel_event and cancel_event.is_set()
    manual_canceled = should_cancel and should_cancel()
    was_canceled = bool(event_canceled or manual_canceled)

    stats: dict[str, float | int] = {
        "num_urls": len(urls),
        "num_success": len(results),
        "num_failed": len(urls) - len(results),
        "duration_sec": duration,
        "was_canceled": was_canceled,
    }

    if job_hooks and hasattr(job_hooks, "on_completed"):
        with contextlib.suppress(Exception):
            job_hooks.on_completed(
                success=stats["num_success"],
                failed=stats["num_failed"],
                duration_sec=stats["duration_sec"],
            )

    return results, stats
