import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from agentic_scraper.backend.api.auth.dependencies import get_current_user
from agentic_scraper.backend.api.auth.scope_helpers import check_required_scopes
from agentic_scraper.backend.api.models import AuthUser, RequiredScopes
from agentic_scraper.backend.api.routes.scrape_cancel_registry import (
    cleanup,
    get_cancel_event,
    register_cancel_event,
    set_canceled,
)
from agentic_scraper.backend.api.routes.scrape_helpers import (
    _finalize_failure,
    _finalize_success_if_not_canceled,
    _mark_running,
    _merge_runtime_settings,
    _resolve_openai_creds_or_fail,
    _run_pipeline_and_build_result,
)
from agentic_scraper.backend.api.schemas.scrape import (
    ScrapeCreate,
    ScrapeJob,
    ScrapeList,
)
from agentic_scraper.backend.api.stores.job_store import (
    cancel_job,
    create_job,
    get_job,
    list_jobs,
)
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_INVALID_JOB_STATUS,
    MSG_HTTP_FORBIDDEN_JOB_ACCESS,
    MSG_HTTP_JOB_NOT_CANCELABLE,
    MSG_HTTP_JOB_NOT_FOUND_DETAIL,
    MSG_HTTP_LOCATION_HEADER_SET,
    MSG_INFO_SCRAPE_REQUEST_RECEIVED,
    MSG_JOB_CANCEL_REQUESTED,
    MSG_JOB_CANCELED,
    MSG_JOB_CREATED,
    MSG_JOB_LIST_REQUESTED,
    MSG_JOB_NOT_FOUND,
)
from agentic_scraper.backend.config.types import AgentMode, JobStatus

router = APIRouter(prefix="/scrapes", tags=["Scrape"])
logger = logging.getLogger(__name__)

CurrentUser = Annotated[AuthUser, Depends(get_current_user)]

# Keep a reference to background tasks (RUF006) and auto-clean when done
_pending_tasks: set[asyncio.Task[None]] = set()


def _track_task(t: asyncio.Task[None]) -> None:
    _pending_tasks.add(t)
    t.add_done_callback(_pending_tasks.discard)


async def _run_scrape_job(job_id: str, payload: ScrapeCreate, user: CurrentUser) -> None:
    """Background job runner that executes the pipeline and updates job state."""
    try:
        _mark_running(job_id)

        creds = _resolve_openai_creds_or_fail(job_id, payload, user)
        # If LLM is required and creds were missing, the helper already failed the job.
        if payload.agent_mode != AgentMode.RULE_BASED and creds is None:
            return

        merged_settings = _merge_runtime_settings(payload)

        cancel_event = get_cancel_event(job_id) or register_cancel_event(job_id)
        # Annotate payload with job_id for downstream _should_cancel closures
        result_model = await _run_pipeline_and_build_result(
            payload=payload,
            merged_settings=merged_settings,
            creds=creds,
            cancel_event=cancel_event,
            job_id=job_id,
        )

        _finalize_success_if_not_canceled(job_id, result_model)

    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:  # noqa: BLE001
        _finalize_failure(job_id, e)
    finally:
        cleanup(job_id)


@router.post(
    "/",
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_scrape_job(
    payload: ScrapeCreate,
    response: Response,
    user: CurrentUser,
    request: Request,
) -> ScrapeJob:
    """
    Create a new scrape job. Returns 202 Accepted with Location to poll the job.
    """
    # Scope: create:scrapes
    check_required_scopes(user, {RequiredScopes.SCRAPES_CREATE})

    logger.info(MSG_INFO_SCRAPE_REQUEST_RECEIVED.format(n=len(payload.urls)))

    # Create queued job (record owner for authorization)
    request_payload = payload.model_dump()
    job = create_job(request_payload, owner_sub=user["sub"])
    logger.info(MSG_JOB_CREATED.format(job_id=job["id"]))

    # Register cancel event at creation to avoid cancel-before-register gaps
    register_cancel_event(job["id"])

    # Schedule background execution explicitly as an asyncio task
    task: asyncio.Task[None] = asyncio.create_task(
        _run_scrape_job(job["id"], payload, user), name=f"scrape-job-{job['id']}"
    )
    _track_task(task)
    # Set Location header for polling (absolute)
    response_url = str(request.url_for("get_scrape_job", job_id=job["id"]))
    response.headers["Location"] = response_url
    logger.info(MSG_HTTP_LOCATION_HEADER_SET.format(url=response_url))

    return ScrapeJob(**job)


@router.get(
    "/{job_id}",
)
async def get_scrape_job(job_id: str, user: CurrentUser) -> ScrapeJob:
    """
    Get a scrape job by id. Includes result when status == 'succeeded'.
    """
    # Scope: read:scrapes
    check_required_scopes(user, {RequiredScopes.SCRAPES_READ})

    job = get_job(job_id)
    if not job:
        logger.warning(MSG_JOB_NOT_FOUND.format(job_id=job_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=MSG_HTTP_JOB_NOT_FOUND_DETAIL
        )

    if job.get("owner_sub") and job["owner_sub"] != user["sub"]:
        logger.warning(MSG_HTTP_FORBIDDEN_JOB_ACCESS.format(user_sub=user["sub"], job_id=job_id))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=MSG_HTTP_FORBIDDEN_JOB_ACCESS
        )

    return ScrapeJob(**job)


@router.get(
    "/",
)
async def list_scrape_jobs(
    user: CurrentUser,
    status_: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> ScrapeList:
    """
    List scrape jobs with optional filtering and pagination.

    Args:
        status_ (str | None): Optional status filter (queued, running, succeeded, failed, canceled).
        limit (int): Max number of jobs to return (default 50).
        cursor (str | None): Opaque cursor for pagination.

    Returns:
        ScrapeList: Items and next_cursor.
    """
    # Scope: read:scrapes
    check_required_scopes(user, {RequiredScopes.SCRAPES_READ})

    logger.info(MSG_JOB_LIST_REQUESTED.format(status=status_, limit=limit, cursor=cursor))

    # Convert query string to enum expected by list_jobs
    status_filter: JobStatus | None = None
    if status_ is not None:
        try:
            status_filter = JobStatus(status_.lower())
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=MSG_ERROR_INVALID_JOB_STATUS.format(status=status_),
            ) from err

    # Filter by owner inside the store so pagination is correct
    items, next_cursor = list_jobs(
        status=status_filter, limit=limit, cursor=cursor, owner_sub=user["sub"]
    )

    return ScrapeList(items=[ScrapeJob(**j) for j in items], next_cursor=next_cursor)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_scrape_job(job_id: str, user: CurrentUser) -> Response:
    """
    Cancel a queued or running scrape job.
    Returns 204 on success, 404 if missing, 409 if not cancelable.
    """
    # Scope: cancel:scrapes
    check_required_scopes(user, {RequiredScopes.SCRAPES_CANCEL})

    logger.info(MSG_JOB_CANCEL_REQUESTED.format(job_id=job_id))

    job = get_job(job_id)
    if not job:
        logger.warning(MSG_JOB_NOT_FOUND.format(job_id=job_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=MSG_HTTP_JOB_NOT_FOUND_DETAIL
        )

    # Ownership check (guarded)
    if job.get("owner_sub") and job["owner_sub"] != user["sub"]:
        logger.warning(MSG_HTTP_FORBIDDEN_JOB_ACCESS.format(user_sub=user["sub"], job_id=job_id))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=MSG_HTTP_FORBIDDEN_JOB_ACCESS
        )

    ok = cancel_job(job_id, user_sub=user["sub"])
    if not ok:
        # Not cancelable (already finished or already canceled)
        current_status = job.get("status")
        if str(current_status).lower() == "canceled":
            # Idempotent: already canceled → 204
            set_canceled(job_id)  # ensure any waiting workers wake up
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=MSG_HTTP_JOB_NOT_CANCELABLE.format(status=current_status),
        )

    logger.info(MSG_JOB_CANCELED.format(job_id=job_id))
    set_canceled(job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
