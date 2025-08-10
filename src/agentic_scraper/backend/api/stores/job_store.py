from __future__ import annotations

import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import TypedDict, Unpack

from agentic_scraper.backend.config.messages import MSG_ERROR_INVALID_JOB_STATUS
from agentic_scraper.backend.config.types import JobStatus

# ----- Types -----------------------------------------------------------------

# Open JSON-ish mapping alias. Using `object` avoids ANN401 while staying flexible.
JSONObj = dict[str, object]

JobResult = JSONObj
JobRequest = JSONObj


class ScrapeJob(TypedDict):
    id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    progress: float
    error: str | None
    result: JobResult | None
    _request: JobRequest


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

# Keys are job IDs; values are job dicts shaped like ScrapeJob.
_STORE: dict[str, ScrapeJob] = {}
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


def _job_snapshot(job: ScrapeJob) -> ScrapeJob:
    """
    Return a deep copy snapshot of the job dict to avoid external mutation.
    """
    return deepcopy(job)


# ----- Public API -------------------------------------------------------------


def create_job(request_payload: JobRequest) -> ScrapeJob:
    """
    Create a new scrape job in 'queued' status.

    Args:
        request_payload (dict[str, object]): The validated request model as a dict
            (e.g., ScrapeCreate.model_dump()).

    Returns:
        ScrapeJob: A job dict shaped for ScrapeJob response
        (id, status, timestamps, progress, error, result, _request).
    """
    job_id = str(uuid.uuid4())
    now = _utcnow()
    job: ScrapeJob = {
        "id": job_id,
        "status": JobStatus.QUEUED,
        "created_at": now,
        "updated_at": now,
        "progress": 0.0,
        "error": None,
        "result": None,
        # Optionally keep a copy of the payload for audit/debug (not exposed publicly).
        "_request": deepcopy(request_payload),
    }
    with _LOCK:
        _STORE[job_id] = job
        return _job_snapshot(job)


def get_job(job_id: str) -> ScrapeJob | None:
    """
    Retrieve a job by its ID.

    Args:
        job_id (str): The job identifier.

    Returns:
        ScrapeJob | None: The job snapshot if found; otherwise None.
    """
    with _LOCK:
        job = _STORE.get(job_id)
        return _job_snapshot(job) if job is not None else None


def update_job(job_id: str, **fields: Unpack[JobUpdateFields]) -> ScrapeJob | None:
    """
    Update a job with the provided fields.

    Common fields include:
        - status (JobStatus or str convertible to JobStatus)
        - progress (float 0..1)
        - error (str | None)
        - result (JobResult | None)
        - updated_at (datetime)

    Args:
        job_id (str): The job identifier.
        **fields: Arbitrary fields to update (validated by JobUpdateFields).

    Returns:
        ScrapeJob | None: The updated job snapshot, or None if not found.
    """
    with _LOCK:
        job = _STORE.get(job_id)
        if job is None:
            return None

        # Coerce first so we always store a JobStatus
        if "status" in fields:
            job["status"] = _coerce_status(fields["status"])

        # Assign fields individually (mypy-friendly; avoid TypedDict.update)
        if "progress" in fields:
            job["progress"] = fields["progress"]
        if "error" in fields:
            job["error"] = fields["error"]
        if "result" in fields:
            # Keep isolation from external mutations
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
) -> tuple[list[ScrapeJob], str | None]:
    """
    List jobs with optional status filtering and a simple cursor for pagination.

    Args:
        status (JobStatus | None): If provided, filter by job status.
        limit (int): Maximum number of jobs to return.
        cursor (str | None): A job_id to start *after* (exclusive).

    Returns:
        tuple[list[ScrapeJob], str | None]:
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


def cancel_job(job_id: str) -> bool:
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
            job.setdefault("error", None)
            return True
        return False
