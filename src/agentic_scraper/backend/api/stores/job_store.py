from __future__ import annotations

import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import TYPE_CHECKING, TypedDict

from typing_extensions import Required, Unpack

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_INVALID_JOB_STATUS,
    MSG_JOB_CANCELED_BY_USER,
)
from agentic_scraper.backend.config.types import JobStatus

# ----- Types -----------------------------------------------------------------

# Open JSON-ish mapping alias. Using `object` avoids ANN401 while staying flexible.
JSONObj = dict[str, object]

JobResult = JSONObj
JobRequest = JSONObj

if TYPE_CHECKING:
    from agentic_scraper.backend.api.models import OwnerSub


class ScrapeJobRecord(TypedDict):
    id: str
    status: JobStatus
    owner_sub: Required[OwnerSub]
    created_at: datetime
    updated_at: datetime
    progress: float
    error: str | None
    result: JobResult | None
    _request: JobRequest
    canceled_by: OwnerSub | None


class JobUpdateFields(TypedDict, total=False):
    """
    Allowed fields for update_job kwargs.

    Notes:
        - `status` accepts either JobStatus or str convertible to JobStatus.
        - `updated_at` can be provided externally; otherwise we auto-refresh.
    """

    status: JobStatus | str
    progress: float
    error: str | None
    result: JobResult | None
    updated_at: datetime


# ----- Internal in-memory store ----------------------------------------------

# Keys are job IDs; values are job dicts shaped like ScrapeJobRecord.
_STORE: dict[str, ScrapeJobRecord] = {}
_LOCK = threading.RLock()

DEFAULT_LIMIT = 50


# ----- Helpers ----------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_status(value: JobStatus | str) -> JobStatus:
    """
    Coerce a status value into a valid JobStatus or raise ValueError.

    Accepts either a JobStatus enum or a string value.
    """
    if isinstance(value, JobStatus):
        return value
    try:
        return JobStatus(value)
    except ValueError as err:
        # Preserve original cause for clearer tracebacks (B904)
        raise ValueError(MSG_ERROR_INVALID_JOB_STATUS.format(status=value)) from err


def _job_snapshot(job: ScrapeJobRecord) -> ScrapeJobRecord:
    """
    Return a deep copy snapshot of the job dict to avoid external mutation.
    """
    return deepcopy(job)


# ----- Public API -------------------------------------------------------------


def create_job(request_payload: JobRequest, owner_sub: OwnerSub) -> ScrapeJobRecord:
    """
    Create a new scrape job in 'queued' status.

    Args:
        request_payload (dict[str, object]): The validated request model as a dict
            (e.g., ScrapeCreate.model_dump()).

    Returns:
        ScrapeJobRecord: A job dict shaped for response
        (id, status, timestamps, progress, error, result, _request).
    """
    job_id = str(uuid.uuid4())
    now = _utcnow()
    job: ScrapeJobRecord = {
        "id": job_id,
        "status": JobStatus.QUEUED,
        "owner_sub": owner_sub,
        "created_at": now,
        "updated_at": now,
        "progress": 0.0,
        "error": None,
        "result": None,
        # Optionally keep a copy of the payload for audit/debug (not exposed publicly).
        "_request": deepcopy(request_payload),
        "canceled_by": None,
    }
    with _LOCK:
        _STORE[job_id] = job
        return _job_snapshot(job)


def get_job(job_id: str) -> ScrapeJobRecord | None:
    """
    Retrieve a job by its ID.

    Args:
        job_id (str): The job identifier.

    Returns:
        ScrapeJobRecord | None: The job snapshot if found; otherwise None.
    """
    with _LOCK:
        job = _STORE.get(job_id)
        return _job_snapshot(job) if job is not None else None


def update_job(job_id: str, **fields: Unpack[JobUpdateFields]) -> ScrapeJobRecord | None:
    """
    Update a job with the provided fields.

    Guards:
        - If the job is already in a terminal state (SUCCEEDED/FAILED/CANCELED),
          ignore status/progress/result/error updates to prevent illegal transitions.

    Returns:
        ScrapeJobRecord | None: The updated job snapshot, or None if not found.
    """
    with _LOCK:
        job = _STORE.get(job_id)
        if job is None:
            return None

        # Determine proposed status (if any), coercing to JobStatus early.
        new_status: JobStatus | None = None
        if "status" in fields:
            new_status = _coerce_status(fields["status"])

        # Hard terminal-state guard: once terminal, do not accept further mutations
        # that change status/progress/result/error. (updated_at may still be set.)
        terminal = {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED}
        if job["status"] in terminal:
            # Drop mutating fields silently; caller gets a snapshot back.
            fields.pop("status", None)
            fields.pop("progress", None)
            fields.pop("result", None)
            fields.pop("error", None)
        # Only apply status if not terminal
        elif new_status is not None:
            job["status"] = new_status

        # Assign fields individually (keep mypy-friendly and preserve deep copies)
        if "progress" in fields:
            job["progress"] = fields["progress"]
        if "error" in fields:
            job["error"] = fields["error"]
        if "result" in fields:
            job["result"] = deepcopy(fields["result"])

        # Ensure updated_at is always refreshed unless explicitly provided
        if "updated_at" in fields and fields["updated_at"] is not None:
            job["updated_at"] = fields["updated_at"]
        else:
            job["updated_at"] = _utcnow()

        return _job_snapshot(job)


def list_jobs(
    *,
    status: JobStatus | None = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[ScrapeJobRecord], str | None]:
    """
    List jobs with optional status filtering and a simple cursor for pagination.

    Args:
        status (JobStatus | None): If provided, filter by job status.
        limit (int): Maximum number of jobs to return.
        cursor (str | None): A job_id to start *after* (exclusive).

    Returns:
        tuple[list[ScrapeJobRecord], str | None]:
            - A list of job snapshots.
            - A next_cursor (job_id) if more results remain; otherwise None.
    """
    with _LOCK:
        # Stable order by created_at then id for deterministic paging
        jobs = sorted(
            _STORE.values(),
            key=lambda j: (j["created_at"], j["id"]),
        )

        if status is not None:
            jobs = [j for j in jobs if j["status"] == status]

        start_idx = 0
        if cursor:
            # Find the index strictly after the cursor id
            for i, j in enumerate(jobs):
                if j["id"] == cursor:
                    start_idx = i + 1
                    break

        safe_limit = max(0, int(limit))
        sliced = jobs[start_idx : start_idx + safe_limit]
        next_cursor = sliced[-1]["id"] if len(sliced) == safe_limit and sliced else None

        return ([_job_snapshot(j) for j in sliced], next_cursor)


def cancel_job(job_id: str, user_sub: OwnerSub) -> bool:
    """
    Best-effort cancel of a job. Marks as 'canceled' if it's in 'queued' or 'running'.

    Note:
        This does not forcibly stop a running task; orchestration code should check
        for canceled status and exit early.

    Args:
        job_id (str): The job identifier.

    Returns:
        bool: True if the job was found and marked canceled; otherwise False.
    """
    with _LOCK:
        job = _STORE.get(job_id)
        if job is None:
            return False
        if job["status"] in {JobStatus.QUEUED, JobStatus.RUNNING}:
            job["status"] = JobStatus.CANCELED
            job["updated_at"] = _utcnow()
            job["canceled_by"] = user_sub
            job["error"] = MSG_JOB_CANCELED_BY_USER.format(job_id=job_id, user_sub=user_sub)
            return True
        return False
