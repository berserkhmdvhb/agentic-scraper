"""
Main entrypoint for the FastAPI backend of Agentic Scraper.

Responsibilities:
- Initialize the FastAPI app instance with versioning and lifespan handlers.
- Apply CORS middleware based on settings and common local-dev hosts.
- Mount versioned route modules (auth, user, scrape) under a shared API prefix.
- Provide a custom OpenAPI generator that injects Auth0-compatible security schemes.
- Expose basic root and health-check routes for monitoring and discovery.

Public API:
- `app`: The ASGI application object to be served by an ASGI server.
- `custom_openapi_for_app`: Wrapper that installs the project's custom OpenAPI schema.
- `health_check`: Liveness/uptime probe endpoint.
- `root`: Minimal index with links (hidden from schema).

Config:
- Domains used for CORS are sourced from settings (`frontend_domain`, `backend_domain`).

Operational:
- Concurrency: Whatever the ASGI server provides (uvicorn/uvicorn workers, etc.).
- Logging: Initialized via `setup_logging()` and settings are logged at startup.

Usage:
    # uvicorn example:
    # uvicorn agentic_scraper.backend.api.main:app --reload

Notes:
- All routers are versioned under `/api/<api_version>`; router modules define their own subpaths.
- The OpenAPI customization is applied by assigning `app.openapi` to `custom_openapi_for_app`.
"""

from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from agentic_scraper import __api_version__ as api_version
from agentic_scraper import __version__ as version
from agentic_scraper.backend.api.lifecycle import lifespan
from agentic_scraper.backend.api.openapi import custom_openapi
from agentic_scraper.backend.api.routes.auth import router as auth_router
from agentic_scraper.backend.api.routes.scrape import router as scrape_router
from agentic_scraper.backend.api.routes.user import router as user_router
from agentic_scraper.backend.core.logger_setup import get_logger, setup_logging
from agentic_scraper.backend.core.settings import get_settings, log_settings

__all__ = ["app"]

# Constants
API_PREFIX = "/api"

# Setup logging early so any import-time logs go through the configured handlers.
setup_logging()
logger = get_logger()
settings = get_settings()
log_settings(settings)

# Versioned API prefix, shared by all routers below.
common_prefix = f"{API_PREFIX}/{api_version}"

# FastAPI app instance
app = FastAPI(
    title="Agentic Scraper API",
    description="FastAPI backend for the Agentic Scraper project",
    version=version,
    lifespan=lifespan,  # startup/shutdown hooks (e.g., JWKS preload, cleanup)
)

# CORS middleware (domains from settings + common local dev hosts)
# Note: `frontend_domain` / `backend_domain` may be empty → filtered out below.
cors_origins = {
    settings.frontend_domain,
    settings.backend_domain,
    "http://localhost:8501",
    "http://127.0.0.1:8501",
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
    Generate (or return cached) OpenAPI schema with custom security schemes.

    Returns:
        dict[str, Any]: The generated OpenAPI schema.

    Notes:
        - Caches the schema in `app.openapi_schema` after the first generation.
    """
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = custom_openapi(app)
    app.openapi_schema = openapi_schema
    return openapi_schema


# Install our OpenAPI factory. FastAPI will call this when serving /openapi.json.
app.openapi = custom_openapi_for_app  # type: ignore[method-assign]


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    """
    Basic health check endpoint.

    Returns:
        dict[str, str]: A small JSON document with service status and version.
    """
    return {"status": "ok", "version": version}


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """
    Root route with simple pointers to docs and version.

    Returns:
        dict[str, str]: Welcome message and useful link paths.
    """
    return {
        "message": "Welcome to Agentic Scraper API",
        "docs": "/docs",
        "version": version,
    }


# Register routers under /api/<version>; each router declares its own subpaths:
# - user router exposes "/user/*"
# - scrape router exposes "/scrapes/*"
# - auth router exposes "/auth/*"
app.include_router(user_router, prefix=common_prefix)
app.include_router(scrape_router, prefix=common_prefix)
app.include_router(auth_router, prefix=common_prefix)
