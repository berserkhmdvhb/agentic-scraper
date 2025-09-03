from __future__ import annotations

import importlib

# Prefer collections.abc over typing for generics (ruff UP035)
from collections.abc import Callable
from datetime import datetime, timezone
from types import ModuleType
from typing import TYPE_CHECKING, TypeAlias
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agentic_scraper.backend.api.schemas.scrape import (
    ScrapeCreate,
    ScrapeJob,
    ScrapeList,
    ScrapeResultDynamic,
    ScrapeResultFixed,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_SCRAPE_CONFIG_MERGED,
    MSG_HTTP_MISSING_OPENAI_CREDS,
    MSG_INFO_INLINE_KEY_MASKED_FALLBACK,
    MSG_JOB_FAILED,
    MSG_JOB_SKIP_MARK_FAILED_TERMINAL,
    MSG_JOB_SKIP_MARK_RUNNING_TERMINAL,
    MSG_JOB_SUCCEEDED,
    MSG_LOG_DEBUG_DYNAMIC_EXTRAS,
    MSG_LOG_DYNAMIC_EXTRAS_ERROR,
)
from agentic_scraper.backend.config.types import AgentMode, JobStatus, OpenAIConfig

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch

    from agentic_scraper.backend.core.settings import Settings as AppSettings

# ----------------------------------------------------------------------------- #
# Constants
# ----------------------------------------------------------------------------- #

EXPECTED_COUNT = 2
FETCH_CONC_VAL = 3
LLM_CONC_VAL = 2
LLM_SCHEMA_RETRIES_VAL = 2
PRESERVED_PROGRESS = 0.7
OPENAI_MODEL_VAL = "gpt-4o"

StoreDict: TypeAlias = dict[str, dict[str, object]]
PatchJobStore: TypeAlias = Callable[[ModuleType, StoreDict | None], StoreDict]

# Private attr names as variables to avoid B009 auto-fix and SLF001
_ATTR_MASKED = "_masked"
_ATTR_MARK_RUNNING = "_mark_running"
_ATTR_RESOLVE_CREDS = "_resolve_openai_creds_or_fail"
_ATTR_MERGE_SETTINGS = "_merge_runtime_settings"
_ATTR_RUN_PIPE = "_run_pipeline_and_build_result"
_ATTR_LOG_EXTRAS = "_debug_log_dynamic_extras"
_ATTR_FINALIZE_SUCCESS = "_finalize_success_if_not_canceled"
_ATTR_FINALIZE_FAILURE = "_finalize_failure"

# ----------------------------------------------------------------------------- #
# Helpers
# ----------------------------------------------------------------------------- #


def _aware_now() -> datetime:
    return datetime.now(timezone.utc)


def _payload(
    *,
    urls: list[str] | None = None,
    agent_mode: AgentMode = AgentMode.LLM_FIXED,
    openai: OpenAIConfig | None = None,
    openai_model: str | None = OPENAI_MODEL_VAL,
) -> ScrapeCreate:
    return ScrapeCreate(
        urls=urls or ["https://a.example"],
        agent_mode=agent_mode,
        openai_credentials=openai,
        openai_model=openai_model,
    )


@pytest.fixture
def sh_mod() -> ModuleType:
    """Import the module under test once per function to keep isolation simple."""
    return importlib.import_module("agentic_scraper.backend.api.routes.scrape_helpers")


# ----------------------------------------------------------------------------- #
# Existing schema tests (kept)
# ----------------------------------------------------------------------------- #


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


def test_scrape_job_accepts_fixed_result_union() -> None:
    created = _aware_now()
    updated = _aware_now()

    job = ScrapeJob.model_validate(
        {
            "id": str(uuid4()),
            "status": JobStatus.SUCCEEDED,
            "created_at": created,
            "updated_at": updated,
            "progress": 1.0,
            "result": ScrapeResultFixed(items=[], stats={"count": 2}).model_dump(),
        }
    )
    assert job.status == JobStatus.SUCCEEDED
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
    assert job.status == JobStatus.SUCCEEDED
    assert isinstance(job.result, (ScrapeResultDynamic, ScrapeResultFixed))


def test_scrape_job_progress_bounds() -> None:
    created = _aware_now()
    updated = _aware_now()

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

    with pytest.raises(ValidationError):
        ScrapeJob.model_validate(
            {
                "id": str(uuid4()),
                "status": JobStatus.RUNNING,
                "created_at": created,
                "updated_at": updated,
                "progress": -0.1,
            }
        )
    with pytest.raises(ValidationError):
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

    j2 = ScrapeJob.model_validate(
        {
            "id": str(uuid4()),
            "status": JobStatus.FAILED,
            "created_at": created,
            "updated_at": updated,
        }
    )
    assert j2.error is None


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
    assert len(lst.items) == EXPECTED_COUNT
    assert dump["next_cursor"] == "cursor-2"


# ----------------------------------------------------------------------------- #
# New tests targeting routes/scrape_helpers.py helpers
# ----------------------------------------------------------------------------- #


def test_masked_true_and_false(sh_mod: ModuleType) -> None:
    masked = getattr(sh_mod, _ATTR_MASKED)
    assert masked("sk-****abcd") is True
    assert masked("plain") is False
    assert masked(None) is False
    assert masked("") is False


def test_mark_running_job_missing_no_crash(
    sh_mod: ModuleType,
    patch_job_store: PatchJobStore,
) -> None:
    _ = patch_job_store(sh_mod, {})
    mark_running = getattr(sh_mod, _ATTR_MARK_RUNNING)
    mark_running("unknown")


@pytest.mark.parametrize("terminal", ["canceled", "succeeded", "failed"])
def test_mark_running_skips_terminal_status(
    sh_mod: ModuleType,
    patch_job_store: PatchJobStore,
    terminal: str,
    caplog_debug: LogCaptureFixture,
) -> None:
    store = patch_job_store(sh_mod, {"j1": {"status": terminal}})
    mark_running = getattr(sh_mod, _ATTR_MARK_RUNNING)
    mark_running("j1")
    assert store["j1"]["status"] == terminal

    expected = MSG_JOB_SKIP_MARK_RUNNING_TERMINAL.format(job_id="j1", status=terminal)
    assert any(expected in r.getMessage() for r in caplog_debug.records)


def test_resolve_creds_masked_inline_falls_back_to_store(
    sh_mod: ModuleType,
    monkeypatch: MonkeyPatch,
    patch_job_store: PatchJobStore,
    caplog_debug: LogCaptureFixture,
) -> None:
    patch_job_store(sh_mod, {"job": {"status": "queued"}})
    masked_cfg = OpenAIConfig(api_key="sk-***masked***", project_id="p-inline")
    payload = _payload(agent_mode=AgentMode.LLM_FIXED, openai=masked_cfg)
    user = {"sub": "u1"}
    returned = OpenAIConfig(api_key="sk-live", project_id="p-store")

    def _fake_loader(_sub: str) -> OpenAIConfig | None:
        return returned

    monkeypatch.setattr(
        "agentic_scraper.backend.api.routes.scrape_helpers.load_user_credentials",
        _fake_loader,
        raising=True,
    )
    resolve = getattr(sh_mod, _ATTR_RESOLVE_CREDS)
    creds = resolve("job", payload, user)

    assert creds == returned
    assert any(MSG_INFO_INLINE_KEY_MASKED_FALLBACK in r.getMessage() for r in caplog_debug.records)


def test_resolve_creds_llm_mode_no_creds_marks_failed(
    sh_mod: ModuleType,
    patch_job_store: PatchJobStore,
    caplog_debug: LogCaptureFixture,
    monkeypatch: MonkeyPatch,
) -> None:
    store = patch_job_store(sh_mod, {"job": {"status": "queued", "progress": 0.0}})
    payload = _payload(agent_mode=AgentMode.LLM_FIXED, openai=None)
    user = {"sub": "u2"}

    def _none_loader(_sub: str) -> OpenAIConfig | None:
        return None

    monkeypatch.setattr(
        "agentic_scraper.backend.api.routes.scrape_helpers.load_user_credentials",
        _none_loader,
        raising=True,
    )
    resolve = getattr(sh_mod, _ATTR_RESOLVE_CREDS)
    creds = resolve("job", payload, user)

    assert creds is None
    snap = store["job"]
    assert snap["status"] == JobStatus.FAILED
    assert snap["error"] == MSG_HTTP_MISSING_OPENAI_CREDS
    # Log assertion: tolerate different templates/usages
    expected_job_only = MSG_JOB_FAILED.format(job_id="job")
    expected_job_error = MSG_JOB_FAILED.format(job_id="job", error=MSG_HTTP_MISSING_OPENAI_CREDS)

    messages = [rec.getMessage() for rec in caplog_debug.records]
    assert any(
        needle in msg
        for msg in messages
        for needle in (expected_job_error, expected_job_only, "job failed")
    )


def test_resolve_creds_rule_based_no_creds_is_ok(
    sh_mod: ModuleType,
    patch_job_store: PatchJobStore,
    monkeypatch: MonkeyPatch,
) -> None:
    store = patch_job_store(sh_mod, {"job": {"status": "queued"}})
    payload = _payload(agent_mode=AgentMode.RULE_BASED, openai=None)
    user = {"sub": "u3"}

    def _none_loader(_sub: str) -> OpenAIConfig | None:
        return None

    monkeypatch.setattr(
        "agentic_scraper.backend.api.routes.scrape_helpers.load_user_credentials",
        _none_loader,
        raising=True,
    )
    resolve = getattr(sh_mod, _ATTR_RESOLVE_CREDS)
    creds = resolve("job", payload, user)

    assert creds is None
    assert store["job"]["status"] == "queued"


def test_merge_runtime_settings_overrides_logged(
    sh_mod: ModuleType,
    caplog_debug: LogCaptureFixture,
) -> None:
    payload = ScrapeCreate(
        urls=["https://a", "https://b"],
        agent_mode=AgentMode.LLM_FIXED,
        openai_model=OPENAI_MODEL_VAL,
        screenshot_enabled=True,
        fetch_concurrency=FETCH_CONC_VAL,
        llm_concurrency=LLM_CONC_VAL,
        retry_attempts=1,
        llm_schema_retries=LLM_SCHEMA_RETRIES_VAL,
    )
    merge = getattr(sh_mod, _ATTR_MERGE_SETTINGS)
    merged = merge(payload)

    assert merged.screenshot_enabled is True
    assert merged.fetch_concurrency == FETCH_CONC_VAL
    assert merged.llm_concurrency == LLM_CONC_VAL
    assert merged.retry_attempts == 1
    assert merged.llm_schema_retries == LLM_SCHEMA_RETRIES_VAL

    # Look for the formatted log (constant is a template with "{config}")
    messages = [r.getMessage() for r in caplog_debug.records]
    joined = " ".join(messages)
    prefix = MSG_DEBUG_SCRAPE_CONFIG_MERGED.split("{config}", 1)[0]

    assert any(m.startswith(prefix) for m in messages)
    for key in ("screenshot_enabled", "fetch_concurrency", "llm_concurrency"):
        assert key in joined


@pytest.mark.asyncio
async def test_run_pipeline_builds_fixed_and_logs_extras(
    sh_mod: ModuleType,
    monkeypatch: MonkeyPatch,
    caplog_debug: LogCaptureFixture,
    settings: AppSettings,
) -> None:
    class _DummyItem:
        def __init__(self, data: dict[str, str]) -> None:
            self._data = data

        def model_dump(self) -> dict[str, str]:
            return self._data

    async def _fake_scrape(
        urls: list[str],
        *,
        settings: object,
        openai: object | None,
        options: object,
    ) -> tuple[list[object], dict[str, object]]:
        # Accept normalized URL with trailing slash
        assert len(urls) == 1
        assert urls[0].rstrip("/") == "https://x"
        _ = (settings, openai, options)
        return [_DummyItem({"url": "https://x/", "title": "A", "author": "B"})], {
            "count": 1,
            "was_canceled": False,
        }

    monkeypatch.setattr(
        "agentic_scraper.backend.api.routes.scrape_helpers.scrape_with_stats",
        _fake_scrape,
        raising=True,
    )
    payload = ScrapeCreate(
        urls=["https://x"],
        agent_mode=AgentMode.LLM_FIXED,
        openai_model=OPENAI_MODEL_VAL,
    )
    run_and_build = getattr(sh_mod, _ATTR_RUN_PIPE)
    result, was_canceled = await run_and_build(
        payload=payload,
        merged_settings=settings,
        creds=None,
        cancel_event=None,
        job_id="job",
    )
    assert isinstance(result, ScrapeResultFixed)
    assert was_canceled is False

    # The constant is a template with {agent_mode}/{keys}; compare using a prefix
    messages = [r.getMessage() for r in caplog_debug.records]
    joined = " ".join(messages)
    prefix = MSG_LOG_DEBUG_DYNAMIC_EXTRAS.split("{agent_mode}", 1)[0]

    assert any(m.startswith(prefix) for m in messages)
    assert "first_item_keys=" in joined


@pytest.mark.asyncio
async def test_run_pipeline_builds_dynamic_and_reports_canceled(
    sh_mod: ModuleType,
    monkeypatch: MonkeyPatch,
    settings: AppSettings,
) -> None:
    class _DummyItem:
        def __init__(self, data: dict[str, str]) -> None:
            self._data = data

        def model_dump(self) -> dict[str, str]:
            return self._data

    async def _fake_scrape(
        urls: list[str],
        *,
        settings: object,
        openai: object | None,
        options: object,
    ) -> tuple[list[object], dict[str, object]]:
        _ = (urls, settings, openai, options)
        return [_DummyItem({"url": "https://y/", "title": "Z"})], {
            "count": 1,
            "was_canceled": True,
        }

    monkeypatch.setattr(
        "agentic_scraper.backend.api.routes.scrape_helpers.scrape_with_stats",
        _fake_scrape,
        raising=True,
    )
    payload = ScrapeCreate(
        urls=["https://y"],
        agent_mode=AgentMode.LLM_DYNAMIC_ADAPTIVE,
        openai_model=OPENAI_MODEL_VAL,
    )
    run_and_build = getattr(sh_mod, _ATTR_RUN_PIPE)
    result, was_canceled = await run_and_build(
        payload=payload,
        merged_settings=settings,
        creds=None,
        cancel_event=None,
        job_id="job",
    )
    assert isinstance(result, ScrapeResultDynamic)
    assert was_canceled is True


def test_debug_log_dynamic_extras_error_path(
    sh_mod: ModuleType,
    caplog_debug: LogCaptureFixture,
) -> None:
    # Create a dummy object whose `.items` is non-subscriptable but truthy,
    # so `items_list[0]` raises TypeError inside the helper.
    class _Weird:
        def __init__(self) -> None:
            self.items = object()

    result_like = _Weird()
    debug_extras = getattr(sh_mod, _ATTR_LOG_EXTRAS)
    debug_extras(result_like, _payload())

    # The constant is a template with "{error}", so compare using a prefix.
    messages = [rec.getMessage() for rec in caplog_debug.records]
    prefix = MSG_LOG_DYNAMIC_EXTRAS_ERROR.split("{error}", 1)[0]
    assert any(msg.startswith(prefix) for msg in messages)


def test_finalize_success_writes_when_not_terminal(
    sh_mod: ModuleType,
    patch_job_store: PatchJobStore,
    caplog_debug: LogCaptureFixture,
) -> None:
    store = patch_job_store(sh_mod, {"job": {"status": "running", "progress": 0.5}})
    result = ScrapeResultFixed(items=[], stats={"count": 0})
    finalize_success = getattr(sh_mod, _ATTR_FINALIZE_SUCCESS)
    finalize_success("job", result)

    snap = store["job"]
    assert snap["status"] == JobStatus.SUCCEEDED
    assert snap["progress"] == 1.0
    assert isinstance(snap["result"], dict)

    # Compare against the formatted message, not the template.
    messages = [rec.getMessage() for rec in caplog_debug.records]
    expected = MSG_JOB_SUCCEEDED.format(job_id="job")
    assert any(expected in msg for msg in messages)


@pytest.mark.parametrize("terminal", ["canceled", "succeeded", "failed"])
def test_finalize_success_respects_terminal_state(
    sh_mod: ModuleType,
    patch_job_store: PatchJobStore,
    terminal: str,
) -> None:
    before = {"status": terminal, "progress": 0.25}
    store = patch_job_store(sh_mod, {"job": before.copy()})
    result = ScrapeResultFixed(items=[], stats={"count": 0})
    finalize_success = getattr(sh_mod, _ATTR_FINALIZE_SUCCESS)
    finalize_success("job", result)
    assert store["job"] == before


def test_finalize_failure_writes_failed_and_preserves_progress(
    sh_mod: ModuleType,
    patch_job_store: PatchJobStore,
    caplog_debug: LogCaptureFixture,
) -> None:
    store = patch_job_store(
        sh_mod,
        {"job": {"status": "running", "progress": PRESERVED_PROGRESS}},
    )
    finalize_failure = getattr(sh_mod, _ATTR_FINALIZE_FAILURE)
    finalize_failure("job", Exception("boom"))

    snap = store["job"]
    assert snap["status"] == "failed"
    assert snap["error"] == "boom"
    assert snap["progress"] == PRESERVED_PROGRESS

    # Check the formatted log (template can vary: with/without {error})
    messages = [rec.getMessage() for rec in caplog_debug.records]
    expected_job_only = MSG_JOB_FAILED.format(job_id="job")
    expected_with_error = MSG_JOB_FAILED.format(job_id="job", error="boom")
    assert any(
        needle in msg
        for msg in messages
        for needle in (expected_with_error, expected_job_only, "job failed: job")
    )


@pytest.mark.parametrize("terminal", ["canceled", "succeeded", "failed"])
def test_finalize_failure_skips_when_terminal(
    sh_mod: ModuleType,
    patch_job_store: PatchJobStore,
    terminal: str,
    caplog_debug: LogCaptureFixture,
) -> None:
    before = {"status": terminal, "progress": 0.9}
    store = patch_job_store(sh_mod, {"job": before.copy()})
    getattr(sh_mod, _ATTR_FINALIZE_FAILURE)("job", Exception("x"))
    assert store["job"] == before

    expected = MSG_JOB_SKIP_MARK_FAILED_TERMINAL.format(job_id="job", status=terminal)
    messages = [rec.getMessage() for rec in caplog_debug.records]
    assert any(expected in msg for msg in messages)
