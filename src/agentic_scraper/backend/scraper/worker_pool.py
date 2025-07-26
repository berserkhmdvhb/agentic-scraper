import asyncio
import logging
from dataclasses import dataclass

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


@dataclass
class WorkerPoolConfig:
    """
    Configuration for running the asynchronous scraping worker pool.

    Encapsulates parameters that control the behavior of the worker pool, including:
    - Whether to take screenshots during scraping.
    - OpenAI credentials used for LLM-based extraction.
    - Concurrency level (number of parallel workers).
    - Maximum size of the task queue.
    - Optional callbacks for handling success and error events.

    This configuration is passed alongside runtime `Settings` to `run_worker_pool`.
    """

    take_screenshot: bool
    openai: OpenAIConfig
    concurrency: int = 10
    max_queue_size: int | None = None
    on_item_processed: OnSuccessCallback | None = None
    on_error: OnErrorCallback | None = None


@dataclass
class _WorkerContext:
    """
    Internal context passed to each worker, bundling settings, credentials,
    screenshot preference, and callbacks.
    """

    settings: Settings
    take_screenshot: bool
    openai: OpenAIConfig
    on_item_processed: OnSuccessCallback | None = None
    on_error: OnErrorCallback | None = None


# ─── Worker Task ───
async def worker(
    *,
    worker_id: int,
    queue: asyncio.Queue[ScrapeInput],
    results: list[ScrapedItem],
    context: _WorkerContext,
) -> None:
    """
    Worker coroutine that consumes scraping tasks from a queue, runs structured extraction,
    and appends successful results.

    Args:
        worker_id (int): ID used for logging/debugging individual workers.
        queue (asyncio.Queue[ScrapeInput]): Queue of (url, cleaned_text) inputs.
        results (list[ScrapedItem]): Shared list where valid results are appended.
        context (WorkerContext): Runtime configuration and shared context for each worker.

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
                    take_screenshot=context.take_screenshot,
                    openai=context.openai,
                )

                item = await extract_structured_data(request, settings=context.settings)

                if item is not None:
                    results.append(item)
                    if context.on_item_processed:
                        context.on_item_processed(item)

            except Exception as e:
                if context.settings.is_verbose_mode:
                    logger.exception(MSG_ERROR_WORKER_FAILED.format(url=url))
                else:
                    logger.warning(MSG_WARNING_WORKER_FAILED_SHORT.format(url=url, error=e))
                if context.on_error:
                    context.on_error(url, e)
            finally:
                if context.settings.is_verbose_mode:
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
    config: WorkerPoolConfig,
) -> list[ScrapedItem]:
    """
    Run concurrent scraping using a worker pool.

    Args:
        inputs (list[ScrapeInput]): List of (url, cleaned_text) tuples.
        settings (Settings): Global scraper configuration.
        config (WorkerPoolConfig):
            Parameters that control scraping behavior and worker pool operation.

    Returns:
        list[ScrapedItem]: Collected structured data items.
    """
    queue: asyncio.Queue[ScrapeInput] = asyncio.Queue(maxsize=config.max_queue_size or 0)
    results: list[ScrapedItem] = []

    if settings.is_verbose_mode:
        logger.info(MSG_INFO_WORKER_POOL_START.format(enabled=config.take_screenshot))

    for input_item in inputs:
        await queue.put(input_item)

    context = _WorkerContext(
        settings=settings,
        take_screenshot=config.take_screenshot,
        openai=config.openai,
        on_item_processed=config.on_item_processed,
        on_error=config.on_error,
    )

    workers = [
        asyncio.create_task(
            worker(
                worker_id=i,
                queue=queue,
                results=results,
                context=context,
            )
        )
        for i in range(config.concurrency)
    ]

    await queue.join()

    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

    return results
