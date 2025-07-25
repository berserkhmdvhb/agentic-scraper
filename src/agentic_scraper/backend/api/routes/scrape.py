from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from agentic_scraper.backend.api.auth.dependencies import get_current_user
from agentic_scraper.backend.api.models import ScrapeRequest, ScrapeResponse
from agentic_scraper.backend.api.user_store import load_user_credentials
from agentic_scraper.backend.config.messages import MSG_INFO_SCRAPE_REQUEST_RECEIVED
from agentic_scraper.backend.core.logger_setup import get_logger
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.backend.scraper.pipeline import scrape_with_stats

router = APIRouter()
settings = get_settings()
logger = get_logger()

# Define a module-level dependency object
CurrentUser = Annotated[dict, Depends(get_current_user)]


@router.post("/scrape")
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
        settings,
        openai_api_key=creds["api_key"],
        openai_project_id=creds["project_id"],
    )

    return ScrapeResponse(results=results, stats=stats)
