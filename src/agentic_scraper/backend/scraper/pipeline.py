import time
from typing import TYPE_CHECKING, Any

from agentic_scraper.backend.config.constants import FETCH_ERROR_PREFIX
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.fetcher import fetch_all
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.backend.scraper.parser import extract_main_text
from agentic_scraper.backend.scraper.worker_pool import run_worker_pool

if TYPE_CHECKING:
    from agentic_scraper.backend.config.types import ScrapeInput


async def scrape_urls(urls: list[str], settings: Settings) -> list[ScrapedItem]:
    """
    Fetch HTML, extract clean text, run LLM worker pool, return all results.

    Args:
        urls (List[str]): List of URLs to scrape.
        settings (Settings): Runtime config (concurrency, screenshot, logging).

    Returns:
        List[ScrapedItem]: Successful results.
    """
    html_by_url = await fetch_all(
        urls=urls,
        settings=settings,
        concurrency=settings.fetch_concurrency,
    )

    scrape_inputs: list[ScrapeInput] = []
    for url, html in html_by_url.items():
        if html.startswith(FETCH_ERROR_PREFIX):
            continue
        text = extract_main_text(html)
        scrape_inputs.append((url, text))

    return await run_worker_pool(
        inputs=scrape_inputs,
        settings=settings,
        concurrency=settings.llm_concurrency,
        take_screenshot=settings.screenshot_enabled,
        log_tracebacks=settings.debug_mode,
    )


async def scrape_with_stats(
    urls: list[str], settings: Settings
) -> tuple[list[ScrapedItem], dict[str, Any]]:
    """
    Run scrape_urls and return results with basic metrics.

    Returns:
        Tuple[List[ScrapedItem], Dict[str, Any]]: Items and stats like duration and success count.
    """
    start = time.perf_counter()
    results = await scrape_urls(urls, settings)
    duration = time.perf_counter() - start

    stats = {
        "num_urls": len(urls),
        "num_success": len(results),
        "num_failed": len(urls) - len(results),
        "duration_sec": round(duration, 2),
    }

    return results, stats
