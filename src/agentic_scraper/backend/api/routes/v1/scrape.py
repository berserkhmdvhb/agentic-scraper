import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from agentic_scraper.backend.api.auth.dependencies import get_current_user
from agentic_scraper.backend.api.schemas.scrape import ScrapeRequest, ScrapeResponse
from agentic_scraper.backend.api.user_store import load_user_credentials
from agentic_scraper.backend.config.messages import MSG_INFO_SCRAPE_REQUEST_RECEIVED
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.backend.scraper.pipeline import scrape_with_stats

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


@router.post("/start", status_code=status.HTTP_202_ACCEPTED, tags=["Scrape"])
async def scrape(
    request: ScrapeRequest,
    user: CurrentUser,

) -> ScrapeResponse:
    logger.info(MSG_INFO_SCRAPE_REQUEST_RECEIVED.format(n=len(request.urls)))

    creds = load_user_credentials(user["sub"])
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OpenAI credentials not found for the authenticated user.",
        )

    results, stats = await scrape_with_stats(
        [str(url) for url in request.urls],
        settings=settings,
        openai=creds,
    )
    return ScrapeResponse(results=results, stats=stats)
