from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from agentic_scraper import __api_version__ as api_version  # PEP8-compliant lowercase
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

# FastAPI app instance
app = FastAPI(
    title="Agentic Scraper API",
    description="FastAPI backend for the Agentic Scraper project",
    version=version,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://agenticscraper.onrender.com",
        "http://localhost:8501",
        "http://127.0.0.1:8000",
        "https://6d35bd763370.ngrok-free.app",
        "http://127.0.0.1:8085",
        "https://6ff4e2a81f86.ngrok-free.app",
        "https://fa8dda17d53a.ngrok-free.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom OpenAPI schema
def custom_openapi_for_app() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = custom_openapi(app)
    app.openapi_schema = openapi_schema
    return openapi_schema


app.openapi = custom_openapi_for_app  # type: ignore[method-assign]


# Health check
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    return {"status": "ok", "version": version}


# Root route
@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"message": "Welcome to Agentic Scraper API", "docs": "/docs", "version": version}


# Register routers with proper /api/v1/ prefix
app.include_router(user_router, prefix=f"{API_PREFIX}/{api_version}/user", tags=["User"])
app.include_router(scrape_router, prefix=f"{API_PREFIX}/{api_version}/scrape", tags=["Scrape"])
app.include_router(auth_router, prefix=f"{API_PREFIX}/{api_version}/auth", tags=["Auth"])
