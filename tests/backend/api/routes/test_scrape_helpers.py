from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from agentic_scraper.backend.api.schemas.scrape import (
    ScrapeJob,
    ScrapeList,
    ScrapeResultDynamic,
    ScrapeResultFixed,
)
from agentic_scraper.backend.config.types import JobStatus


def _aware_now() -> datetime:
    return datetime.now(timezone.utc)


# -----------------------------
# ScrapeResultFixed / ScrapeResultDynamic basics
# -----------------------------
def test_scrape_result_fixed_minimal_ok() -> None:
    res = ScrapeResultFixed(items=[], stats={"count": 0, "duration_sec": 0.12})
    dumped = res.model_dump()
    assert dumped["items"] == []
    assert dumped["stats"]["count"] == 0
    assert "duration_sec" in dumped["stats"]


def test_scrape_result_dynamic_minimal_ok() -> None:
    res = ScrapeResultDynamic(items=[], stats={"count": 0})
    dumped = res.model_dump()
    assert dumped["items"] == []
    assert dumped["stats"]["count"] == 0


# -----------------------------
# ScrapeJob with result unions
# -----------------------------
def test_scrape_job_accepts_fixed_result_union() -> None:
    created = _aware_now()
    updated = _aware_now()

    job = ScrapeJob.model_validate(
        {
            "id": str(uuid4()),
            "status": JobStatus.SUCCEEDED,  # enum is fine here
            "created_at": created,
            "updated_at": updated,
            "progress": 1.0,
            "result": ScrapeResultFixed(items=[], stats={"count": 2}).model_dump(),
        }
    )
    assert job.status == JobStatus.SUCCEEDED
    # Optional extra guard if you want to be explicit:
    # assert str(job.status) == JobStatus.SUCCEEDED.value

    # Don’t force the exact union branch; accept either
    assert isinstance(job.result, (ScrapeResultFixed, ScrapeResultDynamic))

def test_scrape_job_accepts_dynamic_result_union() -> None:
    created = _aware_now()
    updated = _aware_now()

    job = ScrapeJob.model_validate(
        {
            "id": str(uuid4()),
            "status": JobStatus.SUCCEEDED,
            "created_at": created,
            "updated_at": updated,
            "progress": 1.0,
            "result": ScrapeResultDynamic(items=[], stats={"count": 1}).model_dump(),
        }
    )

    # Use equality, not identity
    assert job.status == JobStatus.SUCCEEDED
    # Don’t over-constrain the union branch; Pydantic may resolve to either
    assert isinstance(job.result, (ScrapeResultDynamic, ScrapeResultFixed))


# -----------------------------
# Progress validation & error field presence
# -----------------------------
def test_scrape_job_progress_bounds() -> None:
    created = _aware_now()
    updated = _aware_now()

    # valid bounds
    _ = ScrapeJob.model_validate(
        {
            "id": str(uuid4()),
            "status": JobStatus.RUNNING,
            "created_at": created,
            "updated_at": updated,
            "progress": 0.0,
        }
    )
    _ = ScrapeJob.model_validate(
        {
            "id": str(uuid4()),
            "status": JobStatus.RUNNING,
            "created_at": created,
            "updated_at": updated,
            "progress": 1.0,
        }
    )

    # out of range should fail
    with pytest.raises(Exception):
        ScrapeJob.model_validate(
            {
                "id": str(uuid4()),
                "status": JobStatus.RUNNING,
                "created_at": created,
                "updated_at": updated,
                "progress": -0.1,
            }
        )
    with pytest.raises(Exception):
        ScrapeJob.model_validate(
            {
                "id": str(uuid4()),
                "status": JobStatus.RUNNING,
                "created_at": created,
                "updated_at": updated,
                "progress": 1.1,
            }
        )


def test_scrape_job_failed_has_error_optional() -> None:
    created = _aware_now()
    updated = _aware_now()

    # error present
    j1 = ScrapeJob.model_validate(
        {
            "id": str(uuid4()),
            "status": JobStatus.FAILED,
            "created_at": created,
            "updated_at": updated,
            "error": "boom",
        }
    )
    assert j1.error == "boom"

    # error omitted remains None (model allows it; semantics are handled elsewhere)
    j2 = ScrapeJob.model_validate(
        {
            "id": str(uuid4()),
            "status": JobStatus.FAILED,
            "created_at": created,
            "updated_at": updated,
        }
    )
    assert j2.error is None


# -----------------------------
# ScrapeList pagination wrapper
# -----------------------------
def test_scrape_list_wraps_jobs_and_cursor() -> None:
    now = _aware_now()
    j_fixed = ScrapeJob.model_validate(
        {
            "id": str(uuid4()),
            "status": JobStatus.SUCCEEDED,
            "created_at": now,
            "updated_at": now,
            "progress": 1.0,
            "result": ScrapeResultFixed(items=[], stats={"count": 0}).model_dump(),
        }
    )
    j_dyn = ScrapeJob.model_validate(
        {
            "id": str(uuid4()),
            "status": JobStatus.SUCCEEDED,
            "created_at": now,
            "updated_at": now,
            "progress": 1.0,
            "result": ScrapeResultDynamic(items=[], stats={"count": 0}).model_dump(),
        }
    )

    lst = ScrapeList(items=[j_fixed, j_dyn], next_cursor="cursor-2")
    dump = lst.model_dump()
    assert len(lst.items) == 2
    assert dump["next_cursor"] == "cursor-2"
