"""
Scraping pipeline orchestrator for AgenticScraper.

This module coordinates the full scraping lifecycle:
1. Fetching raw HTML from input URLs.
2. Extracting main textual content.
3. Delegating parsing and data extraction to agent workers via a concurrent pool.

Usage:
    Call `scrape_urls` to run the scraper with a list of URLs and settings.
    Call `scrape_with_stats` to run scraping and receive execution metrics.

Intended for internal use by API route handlers or CLI scripts.
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
    Run the scraping pipeline on the provided URLs using the configured agent mode.
    """
    # Back-compat: allow legacy keyword args (cancel_event, should_cancel, job_hooks)
    if options is None:
        options = PipelineOptions()
    cancel_event = options.cancel_event
    should_cancel = options.should_cancel
    job_hooks = options.job_hooks

    if (cancel_event and cancel_event.is_set()) or (should_cancel and should_cancel()):
        if job_hooks and hasattr(job_hooks, "on_failed"):
            with contextlib.suppress(Exception):
                job_hooks.on_failed(RuntimeError("Scrape canceled before start."))
        return []

    logger.debug(MSG_DEBUG_PIPELINE_FETCH_START.format(count=len(urls)))

    html_by_url = await fetch_all(
        urls=urls,
        settings=settings,
        concurrency=settings.fetch_concurrency,
        cancel_event=cancel_event,
        should_cancel=should_cancel,
    )

    logger.info(MSG_INFO_FETCH_COMPLETE.format(count=len(html_by_url)))

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

    # Early exit if no valid scrape inputs
    if not scrape_inputs:
        if job_hooks and hasattr(job_hooks, "on_completed"):
            with contextlib.suppress(Exception):
                job_hooks.on_completed(success=0, failed=len(urls), duration_sec=0.0)
        return []

    if (cancel_event and cancel_event.is_set()) or (should_cancel and should_cancel()):
        if job_hooks and hasattr(job_hooks, "on_failed"):
            with contextlib.suppress(Exception):
                job_hooks.on_failed(RuntimeError("Scrape canceled before worker pool start."))
        return []

    is_llm_mode = settings.agent_mode in {
        AgentMode.LLM_FIXED,
        AgentMode.LLM_DYNAMIC,
        AgentMode.LLM_DYNAMIC_ADAPTIVE,
    }

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
    Run the scraping pipeline and return both results and performance metrics.
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

    event_canceled = cancel_event and cancel_event.is_set()
    manual_canceled = should_cancel and should_cancel()
    was_canceled = bool(event_canceled or manual_canceled)
    stats = {
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
