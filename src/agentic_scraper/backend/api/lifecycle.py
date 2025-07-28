from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from httpx import TimeoutException

from agentic_scraper.backend.api.auth.auth0_helpers import (
    jwks_cache_instance,  # Import the instance
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_LIFESPAN_STARTED,
    MSG_ERROR_PRELOADING_JWKS,
    MSG_INFO_JWKS_PRELOAD_SUCCESSFUL,  # New constant for success message
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
    """
    try:
        # Startup Logic: Preload JWKS or other resources
        logger.info(MSG_INFO_PRELOADING_JWKS)  # Log that JWKS is being preloaded
        try:
            # Add a timeout for the JWKS fetching operation to avoid hanging indefinitely
            await jwks_cache_instance.get_jwks()  # Use the JWKSCache instance
        except TimeoutException as exc:  # Correctly catching TimeoutException from httpx
            # Log the timeout error
            logger.exception(MSG_ERROR_PRELOADING_JWKS, exc_info=exc)
            # Link the original exception
            raise HTTPException(status_code=503, detail="Timeout fetching JWKS") from exc

        # Successful JWKS preload
        logger.info(MSG_INFO_JWKS_PRELOAD_SUCCESSFUL)  # Use the constant for success message

        # Minimal reference to 'app' to avoid unused argument warning
        logger.debug(MSG_DEBUG_LIFESPAN_STARTED.format(app=app))

        # Yield to indicate that startup is complete and the app can begin receiving requests
        yield

    finally:
        # Shutdown Logic: Clean up resources, close DB connections, etc.
        logger.info(MSG_INFO_SHUTDOWN_LOG)  # Log when the app is shutting down
        # Any other shutdown tasks like closing connections can be added here.
