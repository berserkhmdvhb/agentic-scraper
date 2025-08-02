import asyncio
import logging
from dataclasses import dataclass

from agentic_scraper.backend.config.aliases import (
    OnErrorCallback,
    OnSuccessCallback,
    ScrapeInput,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_WORKER_PICKED_URL,
    MSG_DEBUG_WORKER_CREATED_REQUEST,
    MSG_DEBUG_WORKER_GOT_ITEM,
    MSG_DEBUG_WORKER_ITEM_APPENDED,
    MSG_DEBUG_WORKER_NO_ITEM,
    MSG_DEBUG_WORKER_CANCELLED,
    MSG_DEBUG_POOL_ENQUEUED_URL,
    MSG_DEBUG_POOL_SPAWNED_WORKERS,
    MSG_DEBUG_POOL_CANCELLING_WORKERS,
    MSG_DEBUG_POOL_DONE,
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
            logger.debug(MSG_DEBUG_WORKER_PICKED_URL.format(worker_id=worker_id, url=url))
            try:
                request_kwargs = {
                    "text": text,
                    "url": url,
                    "take_screenshot": context.take_screenshot,
                }
                if context.openai is not None:
                    request_kwargs["openai"] = context.openai

                request = ScrapeRequest(**request_kwargs)
                logger.debug(MSG_DEBUG_WORKER_CREATED_REQUEST.format(worker_id=worker_id, url=url))

                item = await extract_structured_data(request, settings=context.settings)
                logger.debug(MSG_DEBUG_WORKER_GOT_ITEM.format(worker_id=worker_id, item=item))

                if item is not None:
                    results.append(item)
                    logger.debug(MSG_DEBUG_WORKER_ITEM_APPENDED.format(worker_id=worker_id, url=url))
                    if context.on_item_processed:
                        context.on_item_processed(item)
                else:
                    logger.debug(MSG_DEBUG_WORKER_NO_ITEM.format(worker_id=worker_id, url=url))

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
        logger.debug(MSG_DEBUG_WORKER_CANCELLED.format(worker_id=worker_id))
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
        url = input_item[0]
        await queue.put(input_item)
        logger.debug(MSG_DEBUG_POOL_ENQUEUED_URL.format(url=url))

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

    logger.debug(MSG_DEBUG_POOL_SPAWNED_WORKERS.format(count=len(workers)))
    await queue.join()
    logger.debug(MSG_DEBUG_POOL_CANCELLING_WORKERS)

    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

    logger.debug(MSG_DEBUG_POOL_DONE.format(count=len(results)))
    return results
