"""
Main entrypoint for the FastAPI backend of Agentic Scraper.

Responsibilities:
- Initializes the FastAPI app instance with versioning and lifespan.
- Applies CORS middleware for frontend compatibility.
- Mounts all versioned route modules (auth, user, scrape).
- Applies a custom OpenAPI schema with JWT Bearer auth support.
- Exposes basic root and health-check routes.

This file is executed by the ASGI server to start the API.
"""

from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from agentic_scraper import __api_version__ as api_version
from agentic_scraper import __version__ as version
from agentic_scraper.backend.api.lifecycle import lifespan
from agentic_scraper.backend.api.openapi import custom_openapi
from agentic_scraper.backend.api.routes.v1.auth import router as auth_router
from agentic_scraper.backend.api.routes.v1.scrape import router as scrape_router
from agentic_scraper.backend.api.routes.v1.user import router as user_router
from agentic_scraper.backend.core.logger_setup import get_logger, setup_logging
from agentic_scraper.backend.core.settings import get_settings, log_settings

# Constants
API_PREFIX = "/api"

# Setup logging
setup_logging()
logger = get_logger()
settings = get_settings()
log_settings(settings)

common_prefix = f"{API_PREFIX}/{api_version}"

# FastAPI app instance
app = FastAPI(
    title="Agentic Scraper API",
    description="FastAPI backend for the Agentic Scraper project",
    version=version,
    lifespan=lifespan,
)

# CORS middleware (domains from settings + common local dev hosts)
cors_origins = {
    settings.frontend_domain,
    settings.backend_domain,
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in cors_origins if o],  # drop None/empty strings
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def custom_openapi_for_app() -> dict[str, Any]:
    """
    Patch the app's OpenAPI schema to inject custom JWT bearer auth support.

    Returns:
        dict[str, Any]: The generated OpenAPI schema.
    """
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = custom_openapi(app)
    app.openapi_schema = openapi_schema
    return openapi_schema


app.openapi = custom_openapi_for_app  # type: ignore[method-assign]


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    """
    Health check endpoint for uptime and service monitoring.

    Returns:
        dict[str, str]: A simple JSON response with status and version.
    """
    return {"status": "ok", "version": version}


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """
    Root route that redirects to the API documentation.

    Returns:
        dict[str, str]: Welcome message and useful link paths.
    """
    return {
        "message": "Welcome to Agentic Scraper API",
        "docs": "/docs",
        "version": version,
    }


# Register routers under /api/<version>; each router declares its own path segment
# e.g., scrape router exposes "/scrapes", auth router exposes "/auth/*"
app.include_router(user_router, prefix=common_prefix, tags=["User"])
app.include_router(scrape_router, prefix=common_prefix, tags=["Scrape"])
app.include_router(auth_router, prefix=common_prefix, tags=["Auth"])
