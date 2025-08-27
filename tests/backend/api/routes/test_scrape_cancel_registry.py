# tests/backend/api/routes/test_scrape_cancel_registry.py
from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import pytest

from agentic_scraper.backend.api.routes import scrape_cancel_registry as reg

# --- fixtures -----------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_registry() -> Iterator[None]:
    # Ensure a clean slate before/after each test since the module holds globals
    reg.clear_all()
    try:
        yield
    finally:
        reg.clear_all()


# --- helpers ------------------------------------------------------------------

def _jid() -> str:
    return str(uuid.uuid4())


# --- tests --------------------------------------------------------------------

def test_register_returns_event_and_reuses_and_get() -> None:
    jid = _jid()

    ev1 = reg.register_cancel_event(jid)
    assert isinstance(ev1, asyncio.Event)
    assert ev1.is_set() is False

    # get_cancel_event returns the same object
    got = reg.get_cancel_event(jid)
    assert got is ev1

    # registering again reuses the same event instance
    ev2 = reg.register_cancel_event(jid)
    assert ev2 is ev1


def test_set_canceled_before_register_marks_pre_canceled_and_is_set_after_register() -> None:
    jid = _jid()

    # Not registered yet → returns False and remembers pre-canceled
    ok = reg.set_canceled(jid)
    assert ok is False

    # Registering later should produce an already-set event
    ev = reg.register_cancel_event(jid)
    assert isinstance(ev, asyncio.Event)
    assert ev.is_set() is True

    # cleanup removes both the event and the pre-canceled flag
    reg.cleanup(jid)
    assert reg.get_cancel_event(jid) is None

    # Re-register after cleanup → brand new, not set
    ev2 = reg.register_cancel_event(jid)
    assert ev2 is not ev
    assert ev2.is_set() is False


def test_set_canceled_after_register_sets_and_returns_true() -> None:
    jid = _jid()
    ev = reg.register_cancel_event(jid)
    assert ev.is_set() is False

    ok = reg.set_canceled(jid)
    assert ok is True
    assert ev.is_set() is True


def test_cleanup_removes_event_and_pre_canceled_state() -> None:
    jid = _jid()

    ev = reg.register_cancel_event(jid)
    reg.set_canceled(jid)
    assert ev.is_set() is True

    reg.cleanup(jid)

    # Event removed
    assert reg.get_cancel_event(jid) is None

    # Because cleanup also clears pre-canceled, new registration is not set
    ev2 = reg.register_cancel_event(jid)
    assert ev2 is not ev
    assert ev2.is_set() is False


def test_clear_all_clears_both_maps() -> None:
    jid1 = _jid()
    jid2 = _jid()

    # One is registered, the other is set pre-canceled only
    ev1 = reg.register_cancel_event(jid1)
    reg.set_canceled(jid2)
    assert ev1.is_set() is False
    # Not registered yet, so no event to check for jid2

    reg.clear_all()

    # All gone
    assert reg.get_cancel_event(jid1) is None
    assert reg.get_cancel_event(jid2) is None

    # Re-register both: neither should be set since pre-canceled set was cleared
    ev1b = reg.register_cancel_event(jid1)
    ev2b = reg.register_cancel_event(jid2)
    assert ev1b.is_set() is False
    assert ev2b.is_set() is False


def test_invalid_uuid_raises_value_error() -> None:
    bad = "not-a-uuid"

    with pytest.raises(ValueError):
        reg.register_cancel_event(bad)

    with pytest.raises(ValueError):
        reg.get_cancel_event(bad)

    with pytest.raises(ValueError):
        reg.set_canceled(bad)

    with pytest.raises(ValueError):
        reg.cleanup(bad)
