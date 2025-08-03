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
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.fetcher import fetch_all
from agentic_scraper.backend.scraper.models import OpenAIConfig, ScrapedItem
from agentic_scraper.backend.scraper.parser import extract_main_text
from agentic_scraper.backend.scraper.worker_pool import WorkerPoolConfig, run_worker_pool

if TYPE_CHECKING:
    from agentic_scraper.backend.config.aliases import ScrapeInput

logger = logging.getLogger(__name__)


async def scrape_urls(
    urls: list[str],
    settings: Settings,
    openai: OpenAIConfig | None = None,
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

    Returns:
        list[ScrapedItem]: List of successfully scraped and structured items.
    """
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

    is_llm_mode = settings.agent_mode in {
        AgentMode.LLM_FIXED,
        AgentMode.LLM_DYNAMIC,
        AgentMode.LLM_DYNAMIC_ADAPTIVE,
    }

    pool_config = WorkerPoolConfig(
        take_screenshot=settings.screenshot_enabled,
        openai=openai if is_llm_mode else None,
        concurrency=settings.llm_concurrency if is_llm_mode else settings.fetch_concurrency,
    )

    logger.debug(
        MSG_DEBUG_PIPELINE_WORKER_POOL_START.format(count=len(scrape_inputs), is_llm=is_llm_mode)
    )

    return await run_worker_pool(
        inputs=scrape_inputs,
        settings=settings,
        config=pool_config,
    )


async def scrape_with_stats(
    urls: list[str],
    settings: Settings,
    openai: OpenAIConfig | None = None,
) -> tuple[list[ScrapedItem], dict[str, float | int]]:
    """
    Run the scraping pipeline and return both results and performance metrics.

    This function wraps `scrape_urls` and collects timing and outcome statistics.

    Args:
        urls (list[str]): List of URLs to scrape.
        settings (Settings): Runtime scraper configuration.
        openai (OpenAIConfig | None): Optional OpenAI API credentials.

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

    results = await scrape_urls(urls, settings=settings, openai=openai)

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

    return results, stats
