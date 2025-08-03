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

from fastapi import FastAPI, HTTPException
from httpx import TimeoutException

from agentic_scraper.backend.api.auth.auth0_helpers import jwks_cache_instance
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_LIFESPAN_STARTED,
    MSG_ERROR_PRELOADING_JWKS,
    MSG_INFO_JWKS_PRELOAD_SUCCESSFUL,
    MSG_INFO_PRELOADING_JWKS,
    MSG_INFO_SHUTDOWN_LOG,
)
from agentic_scraper.backend.core.logger_setup import get_logger

logger = get_logger()

# Timeout duration for the get_jwks call (in seconds)
JWKS_TIMEOUT = 10


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Preload JWKS from Auth0 during app startup and perform cleanup on shutdown.

    Args:
        app (FastAPI): The FastAPI app instance being managed by this context manager.

    Yields:
        None: Indicates that the app is now ready to serve requests.

    Raises:
        HTTPException: If the JWKS preload times out or fails.
    """
    try:
        # ─── Startup Logic ───
        logger.info(MSG_INFO_PRELOADING_JWKS)
        try:
            await jwks_cache_instance.get_jwks()
        except TimeoutException as exc:
            logger.exception(MSG_ERROR_PRELOADING_JWKS, exc_info=exc)
            raise HTTPException(status_code=503, detail="Timeout fetching JWKS") from exc

        logger.info(MSG_INFO_JWKS_PRELOAD_SUCCESSFUL)
        logger.debug(MSG_DEBUG_LIFESPAN_STARTED.format(app=app))

        yield

    finally:
        # ─── Shutdown Logic ───
        logger.info(MSG_INFO_SHUTDOWN_LOG)
        # Any additional teardown logic (e.g., closing DB sessions) can be added here.
