from fastapi import APIRouter

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
    logger.info(MSG_INFO_SCRAPE_REQUEST_RECEIVED.format(n=len(request.urls)))
    results, stats = await scrape_with_stats([str(url) for url in request.urls], settings)
    return ScrapeResponse(results=results, stats=stats)
