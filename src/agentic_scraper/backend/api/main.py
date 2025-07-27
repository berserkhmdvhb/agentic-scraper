from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from agentic_scraper import __api_version__ as api_version  # Using lowercase for PEP8 compliance
from agentic_scraper import __version__ as version  # Using lowercase for PEP8 compliance
from agentic_scraper.backend.api.lifecycle import lifespan  # Directly use lifespan context here
from agentic_scraper.backend.api.openapi import custom_openapi
from agentic_scraper.backend.api.routes.v1.scrape import router as scrape_router
from agentic_scraper.backend.api.routes.v1.user import router as user_router
from agentic_scraper.backend.core.logger_setup import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger()

# Create FastAPI app instance with lifespan context
app = FastAPI(
    title="Agentic Scraper API",
    description="FastAPI backend for the Agentic Scraper project",
    version=version,  # Using lowercase version variable
    lifespan=lifespan,  # Directly assign the lifespan context here
)

# Register CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://agenticscraper.onrender.com/",  # Allow production frontend
        # Allow local Streamlit for testing
        "http://localhost:8501",
        "http://127.0.0.1:8000",
        "https://bb348695cff1.ngrok-free.app/",
        "http://127.0.0.1:8085",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Enable Swagger UI Bearer Token support by modifying the app.openapi assignment
def custom_openapi_for_app() -> dict[str, Any]:
    """
    Return custom OpenAPI schema with Bearer token support for Swagger UI.
    """
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = custom_openapi(app)
    app.openapi_schema = openapi_schema
    return openapi_schema


app.openapi = custom_openapi_for_app  # type: ignore[method-assign]


# Health check route
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    return {"status": "ok", "version": version}


# Root route (docs redirect)
@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"message": "Welcome to Agentic Scraper API", "docs": "/docs", "version": version}



# Include API routers

app.include_router(user_router, prefix=f"/{api_version}/user", tags=["User"])
app.include_router(scrape_router, prefix=f"/{api_version}/scrape", tags=["Scrape"])
