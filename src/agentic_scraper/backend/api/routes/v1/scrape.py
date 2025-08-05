import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Security, status

from agentic_scraper.backend.api.auth.dependencies import get_current_user
from agentic_scraper.backend.api.schemas.scrape import ScrapeRequest, ScrapeResponse
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.api.user_store import load_user_credentials
from agentic_scraper.backend.config.constants import SCRAPER_CONFIG_FIELDS
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_SCRAPE_CONFIG_MERGED,
    MSG_INFO_SCRAPE_REQUEST_RECEIVED,
)
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.backend.scraper.pipeline import scrape_with_stats

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


@router.post("/start", status_code=status.HTTP_202_ACCEPTED, tags=["Scrape"])
async def scrape(
    request: ScrapeRequest,
    user: CurrentUser | None = Security(get_current_user, auto_error=False),
) -> ScrapeResponse:
    logger.info(MSG_INFO_SCRAPE_REQUEST_RECEIVED.format(n=len(request.urls)))

    if request.agent_mode == AgentMode.RULE_BASED.value:
        # Anonymous scraping allowed
        config_values = request.model_dump(include=set(SCRAPER_CONFIG_FIELDS))
        merged_settings = settings.model_copy(update=config_values)
        logger.debug(MSG_DEBUG_SCRAPE_CONFIG_MERGED.format(config=config_values))

        results, stats = await scrape_with_stats(
            [str(url) for url in request.urls],
            settings=merged_settings,
            openai=None,
        )
        return ScrapeResponse(results=results, stats=stats)

    # All LLM-based agents require authentication
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    creds = request.openai_credentials or load_user_credentials(user["sub"])
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OpenAI credentials not found for the authenticated user.",
        )

    config_values = request.model_dump(include=set(SCRAPER_CONFIG_FIELDS))
    merged_settings = settings.model_copy(update=config_values)
    logger.debug(MSG_DEBUG_SCRAPE_CONFIG_MERGED.format(config=config_values))

    results, stats = await scrape_with_stats(
        [str(url) for url in request.urls],
        settings=merged_settings,
        openai=creds,
    )

    return ScrapeResponse(results=results, stats=stats)
