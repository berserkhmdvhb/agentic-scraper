import asyncio
import logging
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status

from agentic_scraper.backend.api.auth.dependencies import get_current_user
from agentic_scraper.backend.api.schemas.scrape import (
    ScrapeCreate,
    ScrapeJob,
    ScrapeResult,
)
from agentic_scraper.backend.api.stores.job_store import (
    create_job,
    get_job,
    update_job,
)
from agentic_scraper.backend.api.stores.user_store import load_user_credentials
from agentic_scraper.backend.config.constants import SCRAPER_CONFIG_FIELDS
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_SCRAPE_CONFIG_MERGED,
    MSG_INFO_SCRAPE_REQUEST_RECEIVED,
    MSG_JOB_CREATED,
    MSG_JOB_FAILED,
    MSG_JOB_NOT_FOUND,
    MSG_JOB_STARTED,
    MSG_JOB_SUCCEEDED,
)
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.backend.scraper.pipeline import scrape_with_stats

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


async def _run_scrape_job(job_id: str, payload: ScrapeCreate, user: dict[str, Any]) -> None:
    """Background job runner that executes the pipeline and updates job state."""
    try:
        update_job(job_id, status="running", updated_at=datetime.now(timezone.utc))
        logger.info(MSG_JOB_STARTED.format(job_id=job_id))

        # Resolve OpenAI creds (if agent requires them)
        creds = None
        creds = payload.openai_credentials or load_user_credentials(user["sub"])
        if not creds:
            # Fail early if creds are missing for LLM modes
            update_job(
                job_id,
                status="failed",
                error="OpenAI credentials not found for the authenticated user.",
                updated_at=datetime.now(timezone.utc),
            )
            logger.error(MSG_JOB_FAILED.format(job_id=job_id, error="missing_openai_credentials"))
            return

        # Merge runtime settings from request
        config_values = payload.model_dump(include=set(SCRAPER_CONFIG_FIELDS))
        merged_settings = settings.model_copy(update=config_values)
        logger.debug(MSG_DEBUG_SCRAPE_CONFIG_MERGED.format(config=config_values))

        # NOTE: For mid-run progress:
        # wire worker_pool/pipeline progress callbacks to update_job(...)
        # For now, we set progress only at completion.
        urls = [str(u) for u in payload.urls]
        items, stats = await scrape_with_stats(urls, settings=merged_settings, openai=creds)

        # Persist final result
        update_job(
            job_id,
            status="succeeded",
            result=ScrapeResult(items=items, stats=stats).model_dump(),
            progress=1.0,
            updated_at=datetime.now(timezone.utc),
        )
        logger.info(MSG_JOB_SUCCEEDED.format(job_id=job_id))

    except Exception as e:
        update_job(
            job_id,
            status="failed",
            error=str(e),
            updated_at=datetime.now(timezone.utc),
        )
        logger.exception(MSG_JOB_FAILED.format(job_id=job_id))


@router.post(
    "/scrapes",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Scrape"],
)
async def create_scrape_job(
    payload: ScrapeCreate,
    response: Response,
    background: BackgroundTasks,
    user: CurrentUser,
) -> ScrapeJob:
    """
    Create a new scrape job. Returns 202 Accepted with Location to poll the job.
    """
    logger.info(MSG_INFO_SCRAPE_REQUEST_RECEIVED.format(n=len(payload.urls)))

    # Create queued job
    job = create_job(payload.model_dump())
    logger.info(MSG_JOB_CREATED.format(job_id=job["id"]))

    # Schedule background execution
    background.add_task(lambda: asyncio.create_task(_run_scrape_job(job["id"], payload, user)))

    # Set Location header for polling
    response.headers["Location"] = f"/api/v1/scrapes/{job['id']}"
    return ScrapeJob(**job)


@router.get(
    "/scrapes/{job_id}",
    tags=["Scrape"],
)
async def get_scrape_job(job_id: str) -> ScrapeJob:
    """
    Get a scrape job by id. Includes result when status == 'succeeded'.
    """
    job = get_job(job_id)
    if not job:
        logger.warning(MSG_JOB_NOT_FOUND.format(job_id=job_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return ScrapeJob(**job)
