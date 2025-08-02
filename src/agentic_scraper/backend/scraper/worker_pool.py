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
    take_screenshot: bool
    openai: OpenAIConfig | None = None
    concurrency: int = 10
    max_queue_size: int | None = None
    on_item_processed: OnSuccessCallback | None = None
    on_error: OnErrorCallback | None = None


@dataclass
class _WorkerContext:
    settings: Settings
    take_screenshot: bool
    openai: OpenAIConfig | None = None
    on_item_processed: OnSuccessCallback | None = None
    on_error: OnErrorCallback | None = None


async def worker(
    *,
    worker_id: int,
    queue: asyncio.Queue[ScrapeInput],
    results: list[ScrapedItem],
    context: _WorkerContext,
) -> None:
    try:
        while True:
            url, text = await queue.get()
            logger.debug(f"[WORKER {worker_id}] Picked up URL: {url}")
            try:
                request_kwargs = {
                    "text": text,
                    "url": url,
                    "take_screenshot": context.take_screenshot,
                }
                if context.openai is not None:
                    request_kwargs["openai"] = context.openai

                request = ScrapeRequest(**request_kwargs)
                logger.debug(f"[WORKER {worker_id}] Created ScrapeRequest for {url}")

                item = await extract_structured_data(request, settings=context.settings)
                logger.debug(f"[WORKER {worker_id}] extract_structured_data returned: {item}")

                if item is not None:
                    results.append(item)
                    logger.debug(f"[WORKER {worker_id}] ✅ Item appended for URL: {url}")
                    if context.on_item_processed:
                        context.on_item_processed(item)
                else:
                    logger.debug(f"[WORKER {worker_id}] ⚠️ No item returned for URL: {url}")

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
        logger.debug(f"[WORKER {worker_id}] Cancelled during shutdown.")
        pass


async def run_worker_pool(
    inputs: list[ScrapeInput],
    *,
    settings: Settings,
    config: WorkerPoolConfig,
) -> list[ScrapedItem]:
    queue: asyncio.Queue[ScrapeInput] = asyncio.Queue(maxsize=config.max_queue_size or 0)
    results: list[ScrapedItem] = []

    if settings.is_verbose_mode:
        logger.info(MSG_INFO_WORKER_POOL_START.format(enabled=config.take_screenshot))

    for input_item in inputs:
        await queue.put(input_item)
        logger.debug(f"[POOL] Enqueued URL: {input_item[0]}")

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

    logger.debug(f"[POOL] Spawned {len(workers)} workers.")
    await queue.join()
    logger.debug("[POOL] All tasks completed. Cancelling workers...")

    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

    logger.debug(f"[POOL] Worker pool finished. Total results: {len(results)}")
    return results
