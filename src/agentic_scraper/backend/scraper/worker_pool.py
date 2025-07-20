import asyncio
import logging

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_WORKER_FAILED,
    MSG_WARNING_WORKER_FAILED_SHORT,
)
from agentic_scraper.backend.config.types import (
    OnErrorCallback,
    OnSuccessCallback,
    ScrapeInput,
)
from agentic_scraper.backend.scraper.agent import extract_structured_data
from agentic_scraper.backend.scraper.models import ScrapedItem

logger = logging.getLogger(__name__)


# ─── Worker Task ──────────────────────────────────────────────────────────────
async def worker(  # noqa: PLR0913
    *,
    queue: asyncio.Queue[ScrapeInput],
    results: list[ScrapedItem],
    take_screenshot: bool,
    on_item_processed: OnSuccessCallback | None = None,
    on_error: OnErrorCallback | None = None,
    log_tracebacks: bool = False,
) -> None:
    try:
        while True:
            url, text = await queue.get()
            try:
                item = await extract_structured_data(text, url, take_screenshot=take_screenshot)
                if item is not None:
                    results.append(item)

                    if on_item_processed:
                        on_item_processed(item)

            except Exception as e:
                if log_tracebacks:
                    logger.exception(MSG_ERROR_WORKER_FAILED, url)
                else:
                    logger.warning(MSG_WARNING_WORKER_FAILED_SHORT, url, e)
                if on_error:
                    on_error(url, e)
            finally:
                queue.task_done()
    except asyncio.CancelledError:
        # Graceful shutdown
        pass


# ─── Pool Runner ──────────────────────────────────────────────────────────────
async def run_worker_pool(  # noqa: PLR0913
    inputs: list[ScrapeInput],
    *,
    concurrency: int = 10,
    take_screenshot: bool = False,
    max_queue_size: int | None = None,
    on_item_processed: OnSuccessCallback | None = None,
    on_error: OnErrorCallback | None = None,
    log_tracebacks: bool = False,
) -> list[ScrapedItem]:
    """
    Run concurrent scraping using a worker pool.

    Args:
        inputs (list[ScrapeInput]):
            List of (url, cleaned_text) tuples.

        concurrency (int):
            Number of concurrent workers.

        take_screenshot (bool):
            Whether to capture page screenshots.

        max_queue_size (Optional[int]):
            Optional limit on the internal task queue size (default: unlimited).

        on_item_processed (Optional[Callable[[ScrapedItem], None]]):
            Callback called after each successful ScrapedItem is processed.

        on_error (Optional[Callable[[str, Exception], None]]):
            Callback called on error with the URL and exception object.

        log_tracebacks (bool):
            If True, logs full tracebacks on worker failure (default: False).

    Returns:
        list[ScrapedItem]: Collected results.
    """
    queue: asyncio.Queue[ScrapeInput] = asyncio.Queue(maxsize=max_queue_size or 0)
    results: list[ScrapedItem] = []

    for input_item in inputs:
        await queue.put(input_item)

    workers = [
        asyncio.create_task(
            worker(
                queue=queue,
                results=results,
                take_screenshot=take_screenshot,
                on_item_processed=on_item_processed,
                on_error=on_error,
                log_tracebacks=log_tracebacks,
            )
        )
        for _ in range(concurrency)
    ]

    await queue.join()

    for w in workers:
        w.cancel()

    return results
