"""
In-memory job store for scrape orchestration.

Responsibilities:
- Maintain a process-local, thread-safe mapping of job records.
- Provide CRUD-like operations to create, read, update, list, and cancel jobs.
- Enforce terminal-state guards and normalize timestamps/progress.

Public API:
- `create_job`: Insert a new job in QUEUED state.
- `get_job`: Retrieve a deep-copied snapshot of a job by id.
- `update_job`: Mutate selected fields (status/progress/result/error) with guards.
- `list_jobs`: Enumerate jobs with optional status/owner filters and cursor pagination.
- `cancel_job`: Best-effort cancellation for QUEUED/RUNNING jobs.

Operational:
- Concurrency: Thread-safe within a single process via `RLock` (re-entrant).
- Caching/TTL: N/A (entire store is in-memory).
- Logging: Not performed here; callers may log snapshots/results.

Usage:
    from agentic_scraper.backend.api.stores.job_store import create_job, get_job

    job = create_job(request_payload={"urls": ["https://example.com"]}, owner_sub=sub)
    snapshot = get_job(job["id"])

Notes:
- `_STORE` is guarded by a re-entrant lock for thread safety within a single process.
- Snapshots are returned as deep copies to prevent external mutation.
- Once a job is terminal (SUCCEEDED/FAILED/CANCELED), subsequent mutating updates
  to status/progress/result/error are ignored.
- This store is ephemeral and intended for dev/local use. Replace with a DB for prod.
"""

from __future__ import annotations

import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import TYPE_CHECKING, TypedDict

from typing_extensions import Required, Unpack

from agentic_scraper.backend.config.constants import (
    DEFAULT_JOB_LIST_MAX_LIMIT,
    DEFAULT_JOB_LIST_MIN_LIMIT,
)
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_INVALID_JOB_STATUS,
    MSG_JOB_CANCELED_BY_USER,
)
from agentic_scraper.backend.config.types import JobStatus
from agentic_scraper.backend.utils.validators import (
    ensure_utc_aware,
    validate_cursor,
    validate_limit,
    validate_progress,
    validate_uuid,
)

__all__ = [
    "JobUpdateFields",
    "ScrapeJobRecord",
    "cancel_job",
    "create_job",
    "get_job",
    "list_jobs",
    "update_job",
]

# ----- Types -----------------------------------------------------------------

# Open JSON-ish mapping alias. Using `object` avoids ANN401 while staying flexible.
JSONObj = dict[str, object]

JobResult = JSONObj
JobRequest = JSONObj

if TYPE_CHECKING:
    from agentic_scraper.backend.api.models import OwnerSub


class ScrapeJobRecord(TypedDict):
    """Dictionary shape for job records persisted in the in-memory store."""

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
    Allowed fields for `update_job` kwargs.

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
# Re-entrant lock allows nested calls in the same thread if needed.
_LOCK = threading.RLock()


# ----- Helpers ----------------------------------------------------------------


def _utcnow() -> datetime:
    """
    Return the current UTC time as a timezone-aware datetime.

    Returns:
        datetime: Current time in UTC with tzinfo=UTC.
    """
    return datetime.now(timezone.utc)


def _coerce_status(value: JobStatus | str) -> JobStatus:
    """
    Coerce a status value into a valid JobStatus or raise ValueError.

    Accepts either a JobStatus enum or a string value.
    Uses project-specific error message for parity with existing tests.

    Args:
        value (JobStatus | str): Proposed new status.

    Returns:
        JobStatus: Coerced status enum.

    Raises:
        ValueError: If the provided value cannot be converted to a valid JobStatus.

    Examples:
        >>> _coerce_status("queued")
        <JobStatus.QUEUED: 'queued'>
    """
    if isinstance(value, JobStatus):
        return value
    try:
        return JobStatus(value)
    except ValueError as err:
        # Standardized message for tests and API consistency.
        raise ValueError(MSG_ERROR_INVALID_JOB_STATUS.format(status=value)) from err


def _job_snapshot(job: ScrapeJobRecord) -> ScrapeJobRecord:
    """
    Return a deep copy snapshot of the job dict to avoid external mutation.

    Args:
        job (ScrapeJobRecord): The internal job record.

    Returns:
        ScrapeJobRecord: A deep-copied snapshot safe for external use.
    """
    return deepcopy(job)


# ----- Public API -------------------------------------------------------------


def create_job(request_payload: JobRequest, owner_sub: OwnerSub) -> ScrapeJobRecord:
    """
    Create a new scrape job in 'queued' status.

    A copy of the request payload is stored privately under `_request` for
    auditing/debugging and is not exposed in public responses.

    Args:
        request_payload (dict[str, object]): The validated request model as a dict
            (e.g., ScrapeCreate.model_dump()).
        owner_sub (OwnerSub): The job owner's subject identifier.

    Returns:
        ScrapeJobRecord: A job dict shaped for response
        (id, status, timestamps, progress, error, result, _request, canceled_by).

    Notes:
        - Deep-copies the incoming request to avoid later mutation affecting stored state.
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
    # Lock scope kept tight around shared state mutation.
    with _LOCK:
        _STORE[job_id] = job
        return _job_snapshot(job)


def get_job(job_id: str) -> ScrapeJobRecord | None:
    """
    Retrieve a job by its ID.

    Soft-validates the UUID: invalid IDs are treated as "not found" for API stability.

    Args:
        job_id (str): The job identifier.

    Returns:
        ScrapeJobRecord | None: The job snapshot if found; otherwise None.

    Examples:
        >>> snap = get_job("not-a-uuid")
        >>> snap is None
        True
    """
    # Soft-validate ID shape; treat invalid UUID as "not found" to preserve API.
    try:
        validate_uuid(job_id)
    except ValueError:
        return None
    with _LOCK:
        job = _STORE.get(job_id)
        return _job_snapshot(job) if job is not None else None


def update_job(job_id: str, **fields: Unpack[JobUpdateFields]) -> ScrapeJobRecord | None:
    """
    Update a job with the provided fields.

    Guards:
        - If the job is already in a terminal state (SUCCEEDED/FAILED/CANCELED),
          ignore status/progress/result/error updates to prevent illegal transitions.

    Args:
        job_id (str): The job identifier.
        **fields: Fields to update (status/progress/result/error/updated_at).

    Returns:
        ScrapeJobRecord | None: The updated job snapshot, or None if not found.

    Raises:
        ValueError: If a provided 'status' value cannot be coerced to `JobStatus`.

    Notes:
        - `updated_at` is auto-refreshed unless explicitly provided.
        - `result` is deep-copied to decouple external dicts from store internals.
    """
    # Align behavior with get/cancel: invalid IDs behave as "not found".
    try:
        validate_uuid(job_id)
    except ValueError:
        return None

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
        # Only apply status if not terminal.
        elif new_status is not None:
            job["status"] = new_status

        # Assign fields individually (keep mypy-friendly and preserve deep copies).
        if "progress" in fields:
            job["progress"] = validate_progress(fields["progress"])
        if "error" in fields:
            job["error"] = fields["error"]
        if "result" in fields:
            job["result"] = deepcopy(fields["result"])

        # Ensure updated_at is always refreshed unless explicitly provided.
        if "updated_at" in fields and fields["updated_at"] is not None:
            job["updated_at"] = ensure_utc_aware(fields["updated_at"])
        else:
            job["updated_at"] = _utcnow()

        return _job_snapshot(job)


def list_jobs(
    *,
    status: JobStatus | None = None,
    limit: int = DEFAULT_JOB_LIST_MAX_LIMIT,
    cursor: str | None = None,
    owner_sub: OwnerSub | None = None,
) -> tuple[list[ScrapeJobRecord], str | None]:
    """
    List jobs with optional status filtering and a simple cursor for pagination.

    The cursor is the `id` of the last item from the previous page. Results are
    sorted by `(created_at, id)` to provide a stable ordering.

    Args:
        status (JobStatus | None): If provided, filter by job status.
        limit (int): Maximum number of jobs to return.
        cursor (str | None): A job_id to start *after* (exclusive).
        owner_sub (OwnerSub | None): If provided, filter by job owner.

    Returns:
        tuple[list[ScrapeJobRecord], str | None]:
            - A list of job snapshots.
            - A next_cursor (job_id) if more results remain; otherwise None.

    Raises:
        ValueError: If `limit` is out of allowed bounds (via `validate_limit`).

    Notes:
        - Cursor validation is soft (UUID format); invalid cursor is treated as None.
        - Stable ordering ensures deterministic pagination across calls.
    """
    # Validate/normalize cursor (UUID today; could evolve to encoded cursors later).
    cursor = validate_cursor(cursor)
    # Enforce inclusive bounds for limit via centralized validator.
    safe_limit = validate_limit(
        limit, min_value=DEFAULT_JOB_LIST_MIN_LIMIT, max_value=DEFAULT_JOB_LIST_MAX_LIMIT
    )

    with _LOCK:
        # Stable order by created_at then id for deterministic paging.
        jobs = sorted(
            _STORE.values(),
            key=lambda j: (j["created_at"], j["id"]),
        )

        if status is not None:
            jobs = [j for j in jobs if j["status"] == status]

        if owner_sub is not None:
            jobs = [j for j in jobs if j.get("owner_sub") == owner_sub]

        start_idx = 0
        if cursor:
            # Find the index strictly after the cursor id.
            for i, j in enumerate(jobs):
                if j["id"] == cursor:
                    start_idx = i + 1
                    break

        sliced = jobs[start_idx : start_idx + safe_limit]
        # Only provide a next_cursor if there are more jobs beyond this slice.
        has_more = bool(sliced) and (start_idx + len(sliced) < len(jobs))
        next_cursor = sliced[-1]["id"] if has_more else None
        return ([_job_snapshot(j) for j in sliced], next_cursor)


def cancel_job(job_id: str, user_sub: OwnerSub) -> bool:
    """
    Best-effort cancel of a job. Marks as 'canceled' if it's in 'queued' or 'running'.

    Note:
        This does not forcibly stop a running task; orchestration code should check
        for canceled status and exit early.

    Args:
        job_id (str): The job identifier.
        user_sub (OwnerSub): The user who requested cancellation.

    Returns:
        bool: True if the job was found and marked canceled; otherwise False.

    Examples:
        >>> ok = cancel_job("not-a-uuid", user_sub)  # invalid id
        >>> ok
        False
    """
    # Soft-validate ID; invalid UUID acts like "not found".
    try:
        validate_uuid(job_id)
    except ValueError:
        return False

    with _LOCK:
        job = _STORE.get(job_id)
        if job is None:
            return False

        if job["status"] in {JobStatus.QUEUED, JobStatus.RUNNING}:
            job["status"] = JobStatus.CANCELED
            job["updated_at"] = _utcnow()
            job["canceled_by"] = user_sub
            # Record a user-friendly message explaining who canceled which job.
            job["error"] = MSG_JOB_CANCELED_BY_USER.format(job_id=job_id, user_sub=user_sub)
            return True

        return False
