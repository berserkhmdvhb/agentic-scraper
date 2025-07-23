from fastapi import APIRouter, HTTPException

from agentic_scraper.backend.api.models import ScrapeRequest, ScrapeResponse
from agentic_scraper.backend.config.messages import MSG_INFO_SCRAPE_REQUEST_RECEIVED
from agentic_scraper.backend.core.logger_setup import get_logger
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.backend.scraper.pipeline import scrape_with_stats

router = APIRouter()
settings = get_settings()
logger = get_logger()


@router.post("/scrape")
async def scrape(request: ScrapeRequest) -> ScrapeResponse:
    if not request.urls:
        raise HTTPException(status_code=400, detail="No URLs provided.")
    logger.info(MSG_INFO_SCRAPE_REQUEST_RECEIVED, len(request.urls))
    results, stats = await scrape_with_stats(request.urls, settings)
    return ScrapeResponse(results=results, stats=stats)
