"""
FastAPI lifespan handler for startup and shutdown tasks.

This module defines an `asynccontextmanager` for:
- Preloading Auth0 JWKS on app startup.
- Logging the service status and any startup errors.
- Optionally cleaning up resources during shutdown.

The `lifespan` function is passed into the FastAPI app instance.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import TimeoutException

from agentic_scraper.backend.api.auth.auth0_helpers import jwks_cache_instance
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

# Timeout duration for the get_jwks call (in seconds)
JWKS_TIMEOUT = 10


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Preload JWKS from Auth0 during app startup and perform cleanup on shutdown.

    Startup behavior is non-fatal for production readiness: if JWKS preload fails,
    the app will still start and JWKS will be fetched lazily on the first
    authenticated request.

    Args:
        app (FastAPI): The FastAPI app instance being managed by this context manager.

    Returns:
        None: Indicates that the app is now ready to serve requests.
    """
    # ─── Startup Logic ───
    logger.info(MSG_INFO_PRELOADING_JWKS)
    try:
        await jwks_cache_instance.get_jwks()
        logger.info(MSG_INFO_JWKS_PRELOAD_SUCCESSFUL)
    except TimeoutException:
        # Non-fatal: log and proceed; JWKS will be fetched lazily on demand
        logger.exception(MSG_ERROR_PRELOADING_JWKS)
        logger.warning(MSG_WARNING_JWKS_PRELOAD_FAILED_STARTING_LAZILY)
    except Exception:
        logger.exception(MSG_ERROR_PRELOADING_JWKS)
        logger.warning(MSG_WARNING_JWKS_PRELOAD_FAILED_STARTING_LAZILY)

    logger.debug(MSG_DEBUG_LIFESPAN_STARTED.format(app=app))

    try:
        yield
    finally:
        # ─── Shutdown Logic ───
        logger.info(MSG_INFO_SHUTDOWN_LOG)
        # Any additional teardown logic (e.g., closing DB sessions) can be added here.
