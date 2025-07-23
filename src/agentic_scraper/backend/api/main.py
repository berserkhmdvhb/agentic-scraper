from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentic_scraper import __api_version__ as API_VERSION  # noqa: N812
from agentic_scraper import __version__ as VERSION  # noqa: N812
from agentic_scraper.backend.api.routes.scrape import router as scrape_router
from agentic_scraper.backend.core.logger_setup import get_logger, setup_logging

setup_logging()
logger = get_logger()

app = FastAPI(
    title="Agentic Scraper API",
    description="FastAPI backend for the Agentic Scraper project",
    version=VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "version": VERSION}


# Include versioned routes
app.include_router(scrape_router, prefix=f"/{API_VERSION}")
