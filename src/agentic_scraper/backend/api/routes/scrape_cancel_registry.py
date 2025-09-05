"""
In-process registry for scrape job cancellation events.

Responsibilities:
- Maintain a mapping of job IDs → asyncio.Event for cooperative cancellation.
- Support pre-canceling jobs before their event is registered.
- Provide helpers to set, query, and clean up cancellation events.

Public API:
- `register_cancel_event`: Ensure an asyncio.Event exists for a job (creates or reuses).
- `get_cancel_event`: Retrieve the current event for a job (if any).
- `set_canceled`: Mark a job as canceled, setting the event or pre-marking if absent.
- `cleanup`: Remove a job's cancel event and pre-cancel mark.
- `clear_all`: Wipe the entire registry (events and pre-canceled marks).

Operational:
- Concurrency: Safe to use in a single event loop; not thread-safe.
- Logging: Debug-level logs record lifecycle of cancel events.

Usage:
    from agentic_scraper.backend.api.routes.scrape_cancel_registry import (
        register_cancel_event, set_canceled
    )

    ev = register_cancel_event(job_id)
    # later, in another task:
    set_canceled(job_id)
    if ev.is_set():
        print("Job canceled!")

Notes:
- Intended for ephemeral, process-local orchestration; not persistent across restarts.
- Pre-cancel ensures that a cancel request is honored even if the event wasn't created yet.
"""

from __future__ import annotations

import asyncio
import logging

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_CANCEL_EVENT_CLEANED,
    MSG_DEBUG_CANCEL_EVENT_REGISTERED,
    MSG_DEBUG_CANCEL_EVENT_REUSED,
    MSG_DEBUG_CANCEL_EVENT_SET,
)
from agentic_scraper.backend.utils.validators import validate_uuid

# Active cancel events keyed by job_id.
_cancel_events: dict[str, asyncio.Event] = {}
# Job IDs that were canceled before event registration.
_pre_canceled: set[str] = set()
logger = logging.getLogger(__name__)


def clear_all() -> None:
    """
    Clear all registered cancel events and pre-canceled marks.

    Intended primarily for test teardown or process reset.
    """
    _cancel_events.clear()
    _pre_canceled.clear()


def register_cancel_event(job_id: str) -> asyncio.Event:
    """
    Create or retrieve a cancel event for the given job.

    If the job was pre-canceled before event registration, the event is
    returned already set.

    Args:
        job_id (str): Job identifier (validated as UUID).

    Returns:
        asyncio.Event: The cancel event for this job.
    """
    job_id = validate_uuid(job_id)

    ev = _cancel_events.get(job_id)
    if ev is not None:
        logger.debug(MSG_DEBUG_CANCEL_EVENT_REUSED.format(job_id=job_id))
        return ev

    ev = asyncio.Event()
    if job_id in _pre_canceled:
        ev.set()
    _cancel_events[job_id] = ev
    logger.debug(MSG_DEBUG_CANCEL_EVENT_REGISTERED.format(job_id=job_id))
    return ev


def get_cancel_event(job_id: str) -> asyncio.Event | None:
    """
    Retrieve the cancel event for a job, if it exists.

    Args:
        job_id (str): Job identifier (validated as UUID).

    Returns:
        asyncio.Event | None: The registered cancel event, or None if none exists.
    """
    job_id = validate_uuid(job_id)
    return _cancel_events.get(job_id)


def set_canceled(job_id: str) -> bool:
    """
    Mark a job as canceled, setting its event or recording a pre-cancel.

    Args:
        job_id (str): Job identifier (validated as UUID).

    Returns:
        bool: True if an active event was found and set; False if only pre-canceled.
    """
    job_id = validate_uuid(job_id)

    ev = _cancel_events.get(job_id)
    if ev is not None:
        ev.set()
        logger.debug(MSG_DEBUG_CANCEL_EVENT_SET.format(job_id=job_id))
        return True

    _pre_canceled.add(job_id)
    logger.debug(MSG_DEBUG_CANCEL_EVENT_SET.format(job_id=job_id))
    return False


def cleanup(job_id: str) -> None:
    """
    Remove a job's cancel event and pre-cancel mark.

    Args:
        job_id (str): Job identifier (validated as UUID).

    Returns:
        None
    """
    job_id = validate_uuid(job_id)
    _cancel_events.pop(job_id, None)
    _pre_canceled.discard(job_id)
    logger.debug(MSG_DEBUG_CANCEL_EVENT_CLEANED.format(job_id=job_id))
