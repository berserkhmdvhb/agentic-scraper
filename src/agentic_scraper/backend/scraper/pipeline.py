import time
from typing import TYPE_CHECKING

from agentic_scraper.backend.config.constants import FETCH_ERROR_PREFIX
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.fetcher import fetch_all
from agentic_scraper.backend.scraper.models import OpenAIConfig, ScrapedItem
from agentic_scraper.backend.scraper.parser import extract_main_text
from agentic_scraper.backend.scraper.worker_pool import WorkerPoolConfig, run_worker_pool

if TYPE_CHECKING:
    from agentic_scraper.backend.config.aliases import ScrapeInput


async def scrape_urls(
    urls: list[str],
    settings: Settings,
    openai: OpenAIConfig,
) -> list[ScrapedItem]:
    """
    Fetch HTML, extract main text, and run LLM-based extraction with worker pool.

    Args:
        urls (list[str]): List of target URLs.
        settings (Settings): Runtime scraper settings.
        openai (OpenAIConfig): OpenAI credentials for structured extraction.

    Returns:
        list[ScrapedItem]: Successfully extracted structured items.
    """
    html_by_url = await fetch_all(
        urls=urls,
        settings=settings,
        concurrency=settings.fetch_concurrency,
    )

    scrape_inputs: list[ScrapeInput] = [
        (url, extract_main_text(html))
        for url, html in html_by_url.items()
        if not html.startswith(FETCH_ERROR_PREFIX)
    ]

    pool_config = WorkerPoolConfig(
        take_screenshot=settings.screenshot_enabled,
        openai=openai,
        concurrency=settings.llm_concurrency,
    )

    return await run_worker_pool(
        inputs=scrape_inputs,
        settings=settings,
        config=pool_config,
    )


async def scrape_with_stats(
    urls: list[str],
    settings: Settings,
    openai: OpenAIConfig,
) -> tuple[list[ScrapedItem], dict[str, float | int]]:
    """
    Scrape a list of URLs and return structured results with execution metrics.

    Args:
        urls (list[str]): Input URLs to scrape and extract from.
        settings (Settings): Global scraper configuration.
        openai (OpenAIConfig): OpenAI API credentials.

    Returns:
        tuple:
            - list[ScrapedItem]: Extracted structured items.
            - dict[str, float | int]: Statistics on scraping run.
    """
    start = time.perf_counter()

    results = await scrape_urls(urls, settings=settings, openai=openai)

    duration = round(time.perf_counter() - start, 2)

    stats = {
        "num_urls": len(urls),
        "num_success": len(results),
        "num_failed": len(urls) - len(results),
        "duration_sec": duration,
    }

    return results, stats
