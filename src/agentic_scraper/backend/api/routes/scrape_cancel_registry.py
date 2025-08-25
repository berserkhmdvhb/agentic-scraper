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

_cancel_events: dict[str, asyncio.Event] = {}
_pre_canceled: set[str] = set()
logger = logging.getLogger(__name__)


def clear_all() -> None:
    """Clear all registered events AND pre-canceled marks."""
    _cancel_events.clear()
    _pre_canceled.clear()  # ← fix: also clear this


def register_cancel_event(job_id: str) -> asyncio.Event:
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
    job_id = validate_uuid(job_id)
    return _cancel_events.get(job_id)


def set_canceled(job_id: str) -> bool:
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
    job_id = validate_uuid(job_id)
    _cancel_events.pop(job_id, None)
    _pre_canceled.discard(job_id)
    logger.debug(MSG_DEBUG_CANCEL_EVENT_CLEANED.format(job_id=job_id))
