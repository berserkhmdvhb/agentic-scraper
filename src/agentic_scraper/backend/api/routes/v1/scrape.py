import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from agentic_scraper.backend.api.auth.dependencies import get_current_user
from agentic_scraper.backend.api.schemas.scrape import ScrapeRequest, ScrapeResponse
from agentic_scraper.backend.api.user_store import load_user_credentials
from agentic_scraper.backend.config.messages import MSG_INFO_SCRAPE_REQUEST_RECEIVED
from agentic_scraper.backend.config.constants import SCRAPER_CONFIG_FIELDS
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

    creds = None
    if request.agent_mode != "rule_based":
        # Prefer credentials from the request body
        creds = request.openai_credentials

        if not creds:
            # Fallback to user-store credentials
            creds = load_user_credentials(user["sub"])

        if not creds:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="OpenAI credentials not found for the authenticated user.",
            )

    config_values = request.model_dump(include=set(SCRAPER_CONFIG_FIELDS))
    merged_settings = settings.model_copy(update=config_values)
    logger.debug(f"🔧 Backend: config values merged with settings: {config_values}")

    results, stats = await scrape_with_stats(
        [str(url) for url in request.urls],
        settings=merged_settings,
        openai=creds,  # this can now be None
    )

    return ScrapeResponse(results=results, stats=stats)

