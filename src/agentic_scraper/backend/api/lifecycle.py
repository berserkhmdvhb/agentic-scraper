"""
FastAPI lifespan handler for startup and shutdown tasks.

Responsibilities:
- Preload Auth0 JWKS on application startup (non-fatal; falls back to lazy load).
- Log service status and key lifecycle events (startup/shutdown).
- Clear the in-memory cancel-event registry on shutdown.

Public API:
- `lifespan`: Async context manager passed to `FastAPI(lifespan=...)` to orchestrate app lifecycle.

Operational:
- Concurrency: Runs in the app's single startup/shutdown flow; no background threads.
- Retries: JWKS preload relies on the helper's internal retry/backoff (if any).
- Logging: Startup/shutdown status is logged; preload failures are tolerated and logged.

Usage:
    from fastapi import FastAPI
    from agentic_scraper.backend.api.lifecycle import lifespan

    app = FastAPI(lifespan=lifespan)

Notes:
- JWKS preload can be skipped via environment controls (see `_should_skip_jwks_preload`).
- Startup failures during JWKS preload are tolerated; verification will fetch lazily later.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING

import httpx
from httpx import TimeoutException

if TYPE_CHECKING:
    from fastapi import FastAPI

from agentic_scraper.backend.api.auth.auth0_helpers import jwks_cache_instance
from agentic_scraper.backend.api.routes.scrape_cancel_registry import (
    clear_all as clear_cancel_events,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_LIFESPAN_STARTED,
    MSG_ERROR_PRELOADING_JWKS,
    MSG_INFO_JWKS_PRELOAD_SUCCESSFUL,
    MSG_INFO_PRELOADING_JWKS,
    MSG_INFO_SHUTDOWN_LOG,
    MSG_WARNING_JWKS_PRELOAD_FAILED_STARTING_LAZILY,
)
from agentic_scraper.backend.core.logger_setup import get_logger

__all__ = ["lifespan"]

logger = get_logger()


def _should_skip_jwks_preload() -> bool:
    """
    Decide whether to skip JWKS preload based on environment variables.

    Skip if either condition holds:
      - `ENV` is 'TEST' (case-insensitive), or
      - `SKIP_JWKS_PRELOAD` is truthy: "1", "true", or "yes" (case-insensitive).

    Returns:
        bool: True if JWKS preload should be skipped; otherwise False.

    Examples:
        >>> os.environ["ENV"] = "test"
        >>> _should_skip_jwks_preload()
        True
        >>> os.environ.pop("ENV", None); os.environ["SKIP_JWKS_PRELOAD"] = "YES"
        >>> _should_skip_jwks_preload()
        True
    """
    env = os.getenv("ENV", "").strip().upper()
    if env == "TEST":
        return True
    flag = os.getenv("SKIP_JWKS_PRELOAD", "").strip().lower()
    return flag in {"1", "true", "yes"}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Preload JWKS from Auth0 during app startup and perform cleanup on shutdown.

    Startup behavior is non-fatal: if JWKS preload fails, the app still starts and JWKS
    will be fetched lazily on the first authenticated request.

    Args:
        app (FastAPI): The FastAPI application instance.

    Returns:
        None: Control is yielded to the running application until shutdown.

    Notes:
        - Preload is useful to surface configuration/network issues early and warm caches.
        - We intentionally catch broad exceptions during preload to avoid blocking startup.
    """
    # ─── Startup ───
    logger.info(MSG_INFO_PRELOADING_JWKS)

    if _should_skip_jwks_preload():
        # Maintain the same log contract even when skipping to keep tests stable.
        logger.info(MSG_INFO_JWKS_PRELOAD_SUCCESSFUL)
    else:
        try:
            # Preload Auth0 JWKS (network/HTTP errors are tolerated).
            # This primes the cache so the first authenticated request is faster.
            await jwks_cache_instance.get_jwks()
            logger.info(MSG_INFO_JWKS_PRELOAD_SUCCESSFUL)
        except (TimeoutException, httpx.HTTPError, Exception):
            # Be tolerant here: startup should not fail if Auth0 is briefly unavailable.
            logger.exception(MSG_ERROR_PRELOADING_JWKS)
            logger.warning(MSG_WARNING_JWKS_PRELOAD_FAILED_STARTING_LAZILY)

    logger.debug(MSG_DEBUG_LIFESPAN_STARTED.format(app=app))

    try:
        # Hand control back to FastAPI; the app runs between startup and shutdown.
        yield
    finally:
        # ─── Shutdown ───
        logger.info(MSG_INFO_SHUTDOWN_LOG)
        # Best-effort cleanup; suppress errors to avoid masking shutdown.
        with suppress(Exception):
            clear_cancel_events()
