from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import cast

import pytest

from agentic_scraper.backend.api.models import OwnerSub
from agentic_scraper.backend.api.stores import job_store as js
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_INVALID_JOB_STATUS,
    MSG_ERROR_INVALID_PROGRESS,
    MSG_JOB_CANCELED_BY_USER,
)
from agentic_scraper.backend.config.types import JobStatus
from agentic_scraper.backend.utils.validators import validate_uuid4


# ---------- helpers / fixtures ----------

@pytest.fixture(autouse=True)
def _clear_store_between_tests() -> None:
    # Ensure a clean in-memory store for each test
    with js._LOCK:
        js._STORE.clear()


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc)


# ---------- create_job ----------

def test_create_job_basic_fields() -> None:
    urls: list[str] = ["https://a"]
    payload: dict[str, object] = {"urls": urls, "agent_mode": "fixed"}
    owner_sub: OwnerSub = cast(OwnerSub, "auth0|user123")

    job = js.create_job(payload, owner_sub)

    # ID is UUIDv4
    validate_uuid4(job["id"])
    assert job["status"] is JobStatus.QUEUED
    assert job["owner_sub"] == owner_sub
    assert isinstance(job["created_at"], datetime) and job["created_at"].tzinfo is not None
    assert isinstance(job["updated_at"], datetime) and job["updated_at"].tzinfo is not None
    assert job["progress"] == 0.0
    assert job["error"] is None
    assert job["result"] is None
    assert job["canceled_by"] is None

    # _request is a deep copy of the payload
    assert job["_request"] == payload
    # Mutate the original list object; stored copy should not change
    urls.append("https://b")
    assert job["_request"] != payload  # confirm deep copy


def test_create_job_unique_ids() -> None:
    owner_sub: OwnerSub = cast(OwnerSub, "auth0|user123")
    j1 = js.create_job({"n": 1}, owner_sub)
    j2 = js.create_job({"n": 2}, owner_sub)
    assert j1["id"] != j2["id"]
    # Also assert both are valid UUIDv4
    validate_uuid4(j1["id"])
    validate_uuid4(j2["id"])


# ---------- get_job ----------

def test_get_job_returns_deep_copy_and_none_for_unknown() -> None:
    owner_sub: OwnerSub = cast(OwnerSub, "auth0|user123")
    job = js.create_job({"x": 1}, owner_sub)
    jid = job["id"]

    snap1 = js.get_job(jid)
    assert snap1 is not None
    assert snap1 == job

    # mutate snapshot and ensure store is unaffected
    snap1["error"] = "oops"
    snap2 = js.get_job(jid)
    assert snap2 is not None
    assert snap2["error"] is None

    # unknown id → None
    assert js.get_job(str(uuid.uuid4())) is None

    # invalid UUID → None (soft validation)
    assert js.get_job("not-a-uuid") is None


# ---------- update_job ----------

def test_update_job_status_progress_error_result_and_updated_at() -> None:
    owner_sub: OwnerSub = cast(OwnerSub, "auth0|user123")
    job = js.create_job({"x": 1}, owner_sub)
    jid = job["id"]

    # set to RUNNING via string coercion
    updated = js.update_job(jid, status=JobStatus.RUNNING.value, progress=0.25, error=None)
    assert updated is not None
    assert updated["status"] is JobStatus.RUNNING
    assert updated["progress"] == 0.25
    assert updated["error"] is None

    # update result (deep copied)
    data_list: list[int] = [1, 2, 3]
    result_payload: dict[str, object] = {"ok": True, "data": data_list}
    updated2 = js.update_job(jid, result=result_payload)
    assert updated2 is not None
    assert updated2["result"] == {"ok": True, "data": [1, 2, 3]}
    # mutate caller's list, store should not change
    data_list.append(4)
    updated3 = js.get_job(jid)
    assert updated3 is not None
    assert updated3["result"] == {"ok": True, "data": [1, 2, 3]}

    # explicit updated_at must be tz-aware and preserved
    future = _aware(datetime.now(timezone.utc) + timedelta(seconds=5))
    updated4 = js.update_job(jid, updated_at=future)
    assert updated4 is not None
    assert updated4["updated_at"] == future


def test_update_job_invalid_status_and_progress_validation() -> None:
    owner_sub: OwnerSub = cast(OwnerSub, "auth0|user123")
    job = js.create_job({"x": 1}, owner_sub)
    jid = job["id"]

    # invalid status string -> ValueError with expected message
    with pytest.raises(ValueError) as e:
        js.update_job(jid, status="nope")
    assert MSG_ERROR_INVALID_JOB_STATUS.format(status="nope") in str(e.value)

    # invalid progress range -> ValueError
    with pytest.raises(ValueError) as e2:
        js.update_job(jid, progress=1.5)
    assert MSG_ERROR_INVALID_PROGRESS.split("{", 1)[0] in str(e2.value)


def test_update_job_rejects_naive_updated_at() -> None:
    owner_sub: OwnerSub = cast(OwnerSub, "auth0|user123")
    job = js.create_job({"x": 1}, owner_sub)
    jid = job["id"]

    naive = datetime.now()  # naive datetime (no tzinfo)
    with pytest.raises(ValueError):
        js.update_job(jid, updated_at=naive)


def test_update_job_terminal_guard_blocks_mutations() -> None:
    owner_sub: OwnerSub = cast(OwnerSub, "auth0|user123")
    job = js.create_job({"x": 1}, owner_sub)
    jid = job["id"]

    # move to SUCCEEDED
    j1 = js.update_job(jid, status=JobStatus.SUCCEEDED)
    assert j1 is not None and j1["status"] is JobStatus.SUCCEEDED

    # attempts to change status/progress/result/error are ignored
    j2 = js.update_job(
        jid,
        status=JobStatus.RUNNING,
        progress=0.9,
        error="should_be_ignored",
        result={"ignored": True},
    )
    assert j2 is not None
    assert j2["status"] is JobStatus.SUCCEEDED
    assert j2["progress"] == 0.0  # unchanged from initial
    assert j2["error"] is None
    assert j2["result"] is None


# ---------- list_jobs ----------

def test_list_jobs_order_limit_cursor_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    owner_a: OwnerSub = cast(OwnerSub, "auth0|A")
    owner_b: OwnerSub = cast(OwnerSub, "auth0|B")

    # deterministic, unbounded timestamps by patching _utcnow
    base = _aware(datetime(2025, 1, 1, 0, 0, 0))
    tick = {"i": 0}

    def fake_now() -> datetime:
        t = base + timedelta(seconds=tick["i"])
        tick["i"] += 1
        return t

    monkeypatch.setattr(js, "_utcnow", fake_now)

    # create 4 jobs (A, A, B, A)
    j1 = js.create_job({"i": 1}, owner_a)
    j2 = js.create_job({"i": 2}, owner_a)
    j3 = js.create_job({"i": 3}, owner_b)
    j4 = js.create_job({"i": 4}, owner_a)

    # update statuses to have variety
    js.update_job(j2["id"], status=JobStatus.RUNNING)
    js.update_job(j3["id"], status=JobStatus.SUCCEEDED)

    # full list, default limit (>=4), ordered by created_at then id
    items, next_cur = js.list_jobs()
    assert [j["id"] for j in items] == [j1["id"], j2["id"], j3["id"], j4["id"]]
    assert next_cur is None

    # limit=2 -> next_cursor set (since more remain)
    items2, cur2 = js.list_jobs(limit=2)
    assert len(items2) == 2
    assert cur2 == items2[-1]["id"]

    # next page using cursor
    items3, cur3 = js.list_jobs(cursor=cur2)
    assert [j["id"] for j in items3] == [j3["id"], j4["id"]]
    assert cur3 is None  # end reached

    # status filter
    running, _ = js.list_jobs(status=JobStatus.RUNNING)
    assert [j["id"] for j in running] == [j2["id"]]

    # owner_sub filter
    a_only, _ = js.list_jobs(owner_sub=owner_a)
    assert [j["id"] for j in a_only] == [j1["id"], j2["id"], j4["id"]]

    # limit=0 -> empty slice, no next cursor
    empty, cur0 = js.list_jobs(limit=0)
    assert empty == [] and cur0 is None


def test_list_jobs_invalid_cursor_raises() -> None:
    with pytest.raises(ValueError):
        js.list_jobs(cursor="not-a-uuid")


# ---------- cancel_job ----------

def test_cancel_job_from_queued_or_running_sets_fields() -> None:
    owner: OwnerSub = cast(OwnerSub, "auth0|user123")
    job = js.create_job({"x": 1}, owner)
    jid = job["id"]

    # Make it RUNNING and record a previous timestamp
    prev = js.update_job(jid, status=JobStatus.RUNNING)
    assert prev is not None
    prev_updated_at = prev["updated_at"]

    user_sub: OwnerSub = cast(OwnerSub, "auth0|admin")
    ok = js.cancel_job(jid, user_sub=user_sub)
    assert ok is True

    after = js.get_job(jid)
    assert after is not None
    assert after["status"] is JobStatus.CANCELED
    assert after["canceled_by"] == user_sub
    assert after["updated_at"] >= prev_updated_at
    assert after["error"] == MSG_JOB_CANCELED_BY_USER.format(job_id=jid, user_sub=user_sub)

    # second cancel -> False (already terminal)
    assert js.cancel_job(jid, user_sub=user_sub) is False


def test_cancel_job_invalid_or_terminal_returns_false() -> None:
    owner: OwnerSub = cast(OwnerSub, "auth0|user123")
    j_succeeded = js.create_job({"x": 1}, owner)
    js.update_job(j_succeeded["id"], status=JobStatus.SUCCEEDED)

    # Terminal states: False
    assert js.cancel_job(j_succeeded["id"], user_sub=owner) is False

    # Unknown ID: False
    assert js.cancel_job(str(uuid.uuid4()), user_sub=owner) is False

    # Invalid UUID: False (soft validation)
    assert js.cancel_job("not-a-uuid", user_sub=owner) is False
