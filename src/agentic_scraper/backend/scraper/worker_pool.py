import asyncio
import logging

from agentic_scraper.backend.config.aliases import (
    OnErrorCallback,
    OnSuccessCallback,
    ScrapeInput,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_WORKER_PROGRESS,
    MSG_ERROR_WORKER_FAILED,
    MSG_INFO_WORKER_POOL_START,
    MSG_WARNING_WORKER_FAILED_SHORT,
)
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.agent import extract_structured_data
from agentic_scraper.backend.scraper.models import OpenAIConfig, ScrapedItem, ScrapeRequest

logger = logging.getLogger(__name__)


# ─── Worker Task ───
async def worker(
    *,
    worker_id: int,
    queue: asyncio.Queue[ScrapeInput],
    results: list[ScrapedItem],
    settings: Settings,
    take_screenshot: bool,
    openai: OpenAIConfig,
    on_item_processed: OnSuccessCallback | None = None,
    on_error: OnErrorCallback | None = None,
) -> None:
    """
    Worker coroutine that consumes scraping tasks from a queue, runs structured extraction,
    and appends successful results.

    Args:
        worker_id (int): ID used for logging/debugging individual workers.
        queue (asyncio.Queue[ScrapeInput]): Queue of (url, cleaned_text) inputs.
        results (list[ScrapedItem]): Shared list where valid results are appended.
        settings (Settings): Global runtime configuration.
        take_screenshot (bool): Whether to capture screenshots during extraction.
        openai (OpenAIConfig): Encapsulated OpenAI API credentials for the user.
        on_item_processed (Optional[Callable]): Callback called with each ScrapedItem.
        on_error (Optional[Callable]): Callback called with (url, Exception) on failure.

    Returns:
        None
    """
    try:
        while True:
            url, text = await queue.get()
            try:
                request = ScrapeRequest(
                    text=text,
                    url=url,
                    take_screenshot=take_screenshot,
                    openai=openai,
                )

                item = await extract_structured_data(request, settings=settings)

                if item is not None:
                    results.append(item)
                    if on_item_processed:
                        on_item_processed(item)

            except Exception as e:
                if settings.is_verbose_mode:
                    logger.exception(MSG_ERROR_WORKER_FAILED.format(url=url))
                else:
                    logger.warning(MSG_WARNING_WORKER_FAILED_SHORT.format(url=url, error=e))
                if on_error:
                    on_error(url, e)
            finally:
                if settings.is_verbose_mode:
                    logger.debug(
                        MSG_DEBUG_WORKER_PROGRESS.format(
                            worker_id=worker_id,
                            url=url,
                            remaining=queue.qsize() - 1,
                        )
                    )
                queue.task_done()
    except asyncio.CancelledError:
        pass  # graceful shutdown


# ─── Pool Runner ───
async def run_worker_pool(
    inputs: list[ScrapeInput],
    *,
    settings: Settings,
    concurrency: int = 10,
    take_screenshot: bool = False,
    openai: OpenAIConfig,
    max_queue_size: int | None = None,
    on_item_processed: OnSuccessCallback | None = None,
    on_error: OnErrorCallback | None = None,
) -> list[ScrapedItem]:
    """
    Run concurrent scraping using a worker pool.

    Args:
        inputs (list[ScrapeInput]): List of (url, cleaned_text) tuples.
        settings (Settings): Global scraper configuration.
        concurrency (int): Number of concurrent worker tasks.
        take_screenshot (bool): Whether to capture screenshots of pages.
        openai (OpenAIConfig): OpenAI credentials for authenticated API access.
        max_queue_size (Optional[int]): Queue size limit (0 = unlimited).
        on_item_processed (Optional[Callable]): Callback for successful results.
        on_error (Optional[Callable]): Callback for handling errors.

    Returns:
        list[ScrapedItem]: Collected structured data items.
    """
    queue: asyncio.Queue[ScrapeInput] = asyncio.Queue(maxsize=max_queue_size or 0)
    results: list[ScrapedItem] = []

    if settings.is_verbose_mode:
        logger.info(MSG_INFO_WORKER_POOL_START.format(enabled=take_screenshot))

    for input_item in inputs:
        await queue.put(input_item)

    workers = [
        asyncio.create_task(
            worker(
                worker_id=i,
                queue=queue,
                results=results,
                settings=settings,
                take_screenshot=take_screenshot,
                openai=openai,
                on_item_processed=on_item_processed,
                on_error=on_error,
            )
        )
        for i in range(concurrency)
    ]

    await queue.join()

    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

    return results
