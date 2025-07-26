from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agentic_scraper.backend.api.auth.auth0_helpers import get_jwks
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_LIFESPAN_STARTED,
    MSG_INFO_PRELOADING_JWKS,
    MSG_INFO_SHUTDOWN_LOG,
)
from agentic_scraper.backend.core.logger_setup import get_logger

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Preload JWKS from Auth0 during app startup and cleanup on shutdown.

    Args:
        app (FastAPI): The FastAPI app instance.

    Yields:
        None: Indicating that the startup is complete.
    """
    # Startup Logic: Preload JWKS or other resources
    logger.info(MSG_INFO_PRELOADING_JWKS)  # Use the constant for the preloading message
    get_jwks()

    # Minimal reference to 'app' to avoid unused argument warning
    logger.debug(
        MSG_DEBUG_LIFESPAN_STARTED.format(app=app)
    )  # Use the constant for lifespan started message

    # Yield to indicate that startup is complete and the app can begin receiving requests
    yield

    # Shutdown Logic: Clean up resources, close DB connections, etc.
    logger.info(MSG_INFO_SHUTDOWN_LOG)  # Use the constant for the shutdown message
    # Additional cleanup tasks can be added here (e.g., closing DB connections)
