import time
import logging
from typing import TYPE_CHECKING

from agentic_scraper.backend.config.constants import FETCH_ERROR_PREFIX
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
    logger.debug(f"[PIPELINE] Starting scrape_with_stats: agent_mode={settings.agent_mode}, openai_config_provided={openai is not None}")
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
