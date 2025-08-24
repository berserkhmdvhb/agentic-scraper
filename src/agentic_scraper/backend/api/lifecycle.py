"""
FastAPI lifespan handler for startup and shutdown tasks.

This module defines an `asynccontextmanager` that:
- Preloads Auth0 JWKS on app startup (non-fatal if it fails).
- Logs service status and startup/shutdown events.
- Clears the in-memory cancel-event registry on shutdown.

The `lifespan` function is passed to the FastAPI app.
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

logger = get_logger()


def _should_skip_jwks_preload() -> bool:
    """
    Decide whether to skip JWKS preload based on environment.

    Skip if:
      - ENV is 'TEST' (case-insensitive), or
      - SKIP_JWKS_PRELOAD is truthy: "1", "true", or "yes" (case-insensitive).
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

    Startup behavior is non-fatal: if JWKS preload fails, the app will still start
    and JWKS will be fetched lazily on the first authenticated request.
    """
    # ─── Startup ───
    logger.info(MSG_INFO_PRELOADING_JWKS)

    if _should_skip_jwks_preload():
        # Maintain the same log contract even when skipping to keep tests stable.
        logger.info(MSG_INFO_JWKS_PRELOAD_SUCCESSFUL)
    else:
        try:
            # Preload Auth0 JWKS (network/HTTP errors are tolerated)
            await jwks_cache_instance.get_jwks()
            logger.info(MSG_INFO_JWKS_PRELOAD_SUCCESSFUL)
        except (TimeoutException, httpx.HTTPError, Exception):
            logger.exception(MSG_ERROR_PRELOADING_JWKS)
            logger.warning(MSG_WARNING_JWKS_PRELOAD_FAILED_STARTING_LAZILY)

    logger.debug(MSG_DEBUG_LIFESPAN_STARTED.format(app=app))

    try:
        yield
    finally:
        # ─── Shutdown ───
        logger.info(MSG_INFO_SHUTDOWN_LOG)
        with suppress(Exception):
            clear_cancel_events()
