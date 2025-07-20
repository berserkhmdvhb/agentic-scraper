import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, cast

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_PARALLEL_TASK_ABORTED,
    MSG_ERROR_RAY_EXECUTION_FAILED,
    MSG_ERROR_RAY_NOT_INSTALLED,
    MSG_ERROR_RAY_RUNTIME_FAILED,
    MSG_ERROR_TASK_FAILED,
)

logger = logging.getLogger(__name__)

# Try importing Ray (optional dependency)
try:
    import ray

    ray_available = True
except ImportError:
    ray_available = False


def run_parallel(
    fn: Callable[[Any], Any],
    items: Sequence[Any],
    max_workers: int = 4,
    timeout: float | None = None,
    *,
    fail_fast: bool = False,
) -> list[Any]:
    """
    Run tasks in parallel using multiple CPU processes (single-machine).

    Args:
        fn: A picklable function to apply to each item.
        items: Iterable of inputs to process.
        max_workers: Number of CPU workers to use.
        timeout: Optional timeout per task (in seconds).
        fail_fast: If True, abort on first failure.

    Returns:
        List of results, ordered to match input order.
    """
    results: list[Any] = [None] * len(items)
    futures = {}

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for idx, item in enumerate(items):
            future = executor.submit(fn, item)
            futures[future] = idx

        for future in as_completed(futures, timeout=timeout):
            idx = futures[future]
            try:
                result = future.result()
                results[idx] = result
            except Exception:
                logger.exception(MSG_ERROR_TASK_FAILED.format(idx=idx, error="Unhandled exception"))
                if fail_fast:
                    raise RuntimeError(MSG_ERROR_PARALLEL_TASK_ABORTED.format(idx=idx)) from None

    return results


def run_distributed_parallel(
    fn: Callable[[Any], Any],
    items: list[Any],
    max_concurrency: int = 4,
) -> list[Any]:
    """
    Run tasks in distributed parallel using Ray (if installed).

    Args:
        fn: A picklable function to apply to each item.
        items: List of items to process.
        max_concurrency: Max parallel Ray tasks.

    Returns:
        List of results in the same order as inputs.
    """
    if not ray_available:
        raise ImportError(MSG_ERROR_RAY_NOT_INSTALLED)

    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, include_dashboard=False, num_cpus=max_concurrency)

    remote_fn = ray.remote(fn)
    futures = [remote_fn.remote(item) for item in items]

    try:
        results = cast("list[Any]", ray.get(futures))
    except Exception as e:
        logger.exception(MSG_ERROR_RAY_EXECUTION_FAILED)
        raise RuntimeError(MSG_ERROR_RAY_RUNTIME_FAILED) from e
    finally:
        ray.shutdown()

    return results
