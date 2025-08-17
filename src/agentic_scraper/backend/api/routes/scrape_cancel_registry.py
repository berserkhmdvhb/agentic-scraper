import asyncio
import logging

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_CANCEL_EVENT_CLEANED,
    MSG_DEBUG_CANCEL_EVENT_REGISTERED,
    MSG_DEBUG_CANCEL_EVENT_REUSED,
    MSG_DEBUG_CANCEL_EVENT_SET,
)

_cancel_events: dict[str, asyncio.Event] = {}
_pre_canceled: set[str] = set()
logger = logging.getLogger(__name__)


def clear_all() -> None:
    _cancel_events.clear()


def register_cancel_event(job_id: str) -> asyncio.Event:
    # Reuse existing to preserve prior set() state
    ev = _cancel_events.get(job_id)
    if ev is not None:
        logger.debug(MSG_DEBUG_CANCEL_EVENT_REUSED.format(job_id=job_id))
        return ev
    ev = asyncio.Event()
    # If job was canceled before registration, reflect it immediately
    if job_id in _pre_canceled:
        ev.set()
    _cancel_events[job_id] = ev
    logger.debug(MSG_DEBUG_CANCEL_EVENT_REGISTERED.format(job_id=job_id))
    return ev


def get_cancel_event(job_id: str) -> asyncio.Event | None:
    return _cancel_events.get(job_id)


def set_canceled(job_id: str) -> bool:
    ev = _cancel_events.get(job_id)
    if ev:
        ev.set()
        logger.debug(MSG_DEBUG_CANCEL_EVENT_SET.format(job_id=job_id))
        return True
    # Not registered yet—remember
    # it so future register() returns a set event
    _pre_canceled.add(job_id)
    logger.debug(MSG_DEBUG_CANCEL_EVENT_SET.format(job_id=job_id))
    return False


def cleanup(job_id: str) -> None:
    _cancel_events.pop(job_id, None)
    _pre_canceled.discard(job_id)
    logger.debug(MSG_DEBUG_CANCEL_EVENT_CLEANED.format(job_id=job_id))
