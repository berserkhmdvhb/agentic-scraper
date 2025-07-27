from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from agentic_scraper.backend.api.auth.auth0_helpers import get_jwks
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_LIFESPAN_STARTED,
    MSG_ERROR_PRELOADING_JWKS,
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

    This context manager handles the startup and shutdown lifecycle of the app,
    such as preloading resources (e.g., JWKS) during startup and performing
    necessary cleanup tasks during shutdown.

    Args:
        app (FastAPI): The FastAPI app instance that is being managed by this context manager.

    Yields:
        None: Indicates that the app is now ready to serve requests.
    """
    try:
        # Startup Logic: Preload JWKS or other resources
        logger.info(MSG_INFO_PRELOADING_JWKS)  # Log that JWKS is being preloaded
        try:
            # Add a timeout for the JWKS fetching operation to avoid hanging indefinitely
            await get_jwks()  # Ensure this is async if needed
        except TimeoutError as exc:  # Use the built-in TimeoutError directly
            # Log the timeout error
            logger.exception(MSG_ERROR_PRELOADING_JWKS, exc_info=exc)
            # Link the original exception
            raise HTTPException(status_code=503, detail="Timeout fetching JWKS") from exc

        # Minimal reference to 'app' to avoid unused argument warning
        # Use the constant for lifespan started message
        logger.debug(MSG_DEBUG_LIFESPAN_STARTED.format(app=app))

        # Yield to indicate that startup is complete and the app can begin receiving requests
        yield

    finally:
        # Shutdown Logic: Clean up resources, close DB connections, etc.
        logger.info(MSG_INFO_SHUTDOWN_LOG)  # Log when the app is shutting down
        # Any other shutdown tasks like closing connections can be added here.
