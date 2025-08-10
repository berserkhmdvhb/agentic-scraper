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
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.scraper.fetcher import fetch_all
from agentic_scraper.backend.scraper.models import WorkerPoolConfig
from agentic_scraper.backend.scraper.parser import extract_main_text
from agentic_scraper.backend.scraper.worker_pool import run_worker_pool

if TYPE_CHECKING:
    from agentic_scraper.backend.config.aliases import ScrapeInput
    from agentic_scraper.backend.core.settings import Settings
    from agentic_scraper.backend.scraper.models import OpenAIConfig, ScrapedItem

logger = logging.getLogger(__name__)


async def scrape_urls(
    urls: list[str],
    settings: Settings,
    openai: OpenAIConfig | None = None,
    *,
    cancel_event: asyncio.Event | None = None,
    job_hooks: object | None = None,
) -> list[ScrapedItem]:
    """
    Run the scraping pipeline on the provided URLs using the configured agent mode.

    This function:
    - Fetches HTML content for each URL.
    - Extracts the main text from HTML.
    - Runs the extraction workers with LLM or non-LLM agents.

    Args:
        urls (list[str]): List of target URLs to scrape.
        settings (Settings): Runtime settings (agent mode, concurrency, etc.).
        openai (OpenAIConfig | None): OpenAI credentials for LLM agents. Optional.
        cancel_event (asyncio.Event | None): If set during execution, the pipeline should
            stop early where possible. (Checked before worker dispatch; deeper checks can
            be added in worker_pool.)
        job_hooks (object | None): Optional object with any of:
            - on_started(total: int) -> None
            - on_completed(success: int, failed: int, duration_sec: float) -> None
            - on_failed(error: Exception) -> None

    Returns:
        list[ScrapedItem]: List of successfully scraped and structured items.
    """
    if cancel_event and cancel_event.is_set():
        if job_hooks and hasattr(job_hooks, "on_failed"):
            with contextlib.suppress(Exception):
                job_hooks.on_failed(RuntimeError("Scrape canceled before start."))
        return []

    logger.debug(MSG_DEBUG_PIPELINE_FETCH_START.format(count=len(urls)))

    html_by_url = await fetch_all(
        urls=urls,
        settings=settings,
        concurrency=settings.fetch_concurrency,
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
    
    # early exit if no valid scrape inputs
    if not scrape_inputs:
        if job_hooks and hasattr(job_hooks, "on_completed"):
            with contextlib.suppress(Exception):
                job_hooks.on_completed(success=0, failed=len(urls), duration_sec=0.0)
        return []
    
    if cancel_event and cancel_event.is_set():
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
    )

    logger.debug(
        MSG_DEBUG_PIPELINE_WORKER_POOL_START.format(count=len(scrape_inputs), is_llm=is_llm_mode)
    )

    return await run_worker_pool(
        inputs=scrape_inputs,
        settings=settings,
        config=pool_config,
        cancel_event=cancel_event,
    )


async def scrape_with_stats(
    urls: list[str],
    settings: Settings,
    openai: OpenAIConfig | None = None,
    *,
    cancel_event: asyncio.Event | None = None,
    job_hooks: object | None = None,
) -> tuple[list[ScrapedItem], dict[str, float | int]]:
    """
    Run the scraping pipeline and return both results and performance metrics.

    This function wraps `scrape_urls` and collects timing and outcome statistics.

    Args:
        urls (list[str]): List of URLs to scrape.
        settings (Settings): Runtime scraper configuration.
        openai (OpenAIConfig | None): Optional OpenAI API credentials.
        cancel_event (asyncio.Event | None): Optional cancellation signal to stop early.
        job_hooks (object | None): Optional lifecycle hooks:
            - on_started(total: int) -> None
            - on_completed(success: int, failed: int, duration_sec: float) -> None
            - on_failed(error: Exception) -> None

    Returns:
        tuple[list[ScrapedItem], dict[str, float | int]]:
            - List of successfully scraped items.
            - Dictionary of scrape stats including duration and counts.
    """
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
            cancel_event=cancel_event,
            job_hooks=job_hooks,
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

    stats = {
        "num_urls": len(urls),
        "num_success": len(results),
        "num_failed": len(urls) - len(results),
        "duration_sec": duration,
    }

    if job_hooks and hasattr(job_hooks, "on_completed"):
        with contextlib.suppress(Exception):
            job_hooks.on_completed(
                success=stats["num_success"],
                failed=stats["num_failed"],
                duration_sec=stats["duration_sec"],
            )

    return results, stats
