# tests/backend/scraper/test_models.py
from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import ValidationError

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_EMPTY_STRING,
    MSG_ERROR_INVALID_PRICE_FORMAT,
)
from agentic_scraper.backend.scraper.models import (
    RetryContext,
    ScrapeRequest,
    WorkerPoolConfig,
)
from agentic_scraper.backend.scraper.schemas import (
    PipelineOutput,
    PipelineStats,
    ScrapedItem,
)

# ------------------------ Test constants to avoid "magic numbers" ------------------------ #

BEST_SCORE = 0.85
BEST_VALID_SCORE = 0.8

PIPE_TOTAL = 3
PIPE_SUCCEEDED = 2
PIPE_FAILED = 1
PIPE_DURATION = 1.234

DEFAULT_CONCURRENCY = 10
CUSTOM_CONCURRENCY = 3
CUSTOM_MAX_QUEUE = 50


# ------------------------------------ ScrapeRequest ------------------------------------- #


def test_scrape_request_minimal() -> None:
    sr = ScrapeRequest(text="hello world", url="https://example.com/page")
    assert sr.text == "hello world"
    assert sr.url == "https://example.com/page"
    # defaults
    assert sr.take_screenshot is False
    assert sr.openai is None
    assert sr.context_hints is None


def test_scrape_request_full() -> None:
    hints: dict[str, str] = {"category": "blog", "lang": "en"}
    sr = ScrapeRequest(
        text="content",
        url="http://example.org",
        take_screenshot=True,
        openai=None,
        context_hints=hints,
    )
    assert sr.take_screenshot is True
    assert sr.context_hints == {"category": "blog", "lang": "en"}


def test_scrape_request_rejects_blank_text() -> None:
    with pytest.raises(ValidationError) as ei:
        ScrapeRequest(text="   ", url="https://example.com")
    assert MSG_ERROR_EMPTY_STRING.format(field="text") in str(ei.value)


def test_scrape_request_context_hints_trim_and_reject_empty() -> None:
    # trims:
    sr = ScrapeRequest(
        text="x",
        url="https://example.com",
        context_hints={"  k  ": "  v  "},
    )
    assert sr.context_hints == {"k": "v"}

    # rejects empty key or value:
    with pytest.raises(ValueError, match=r".*"):
        ScrapeRequest(text="x", url="https://example.com", context_hints={"": "v"})
    with pytest.raises(ValueError, match=r".*"):
        ScrapeRequest(text="x", url="https://example.com", context_hints={"k": ""})


# ------------------------------------ RetryContext -------------------------------------- #


def _fake_msg(role: str, content: str) -> dict[str, Any]:
    # ChatCompletionMessageParam is a TypedDict; a minimal dict suffices at runtime
    return {"role": role, "content": content}


def test_retry_context_mutability() -> None:
    messages: list[dict[str, Any]] = [
        _fake_msg("user", "prompt"),
        _fake_msg("assistant", '{"title": "T"}'),
    ]

    rc = RetryContext(
        messages=cast("list[Any]", messages),
        best_score=0.0,
        best_valid_score=0.0,
        best_fields=None,
        best_valid_item=None,  # ScrapedItem not required for this test
        all_fields={},
        has_done_discovery=False,
    )

    # mutate and ensure fields track
    rc.best_score = BEST_SCORE
    rc.best_valid_score = BEST_VALID_SCORE
    rc.best_fields = {"title": "New"}
    rc.all_fields = {"title": "New", "author": "A"}
    rc.has_done_discovery = True

    assert rc.best_score == BEST_SCORE
    assert rc.best_valid_score == BEST_VALID_SCORE
    assert rc.best_fields == {"title": "New"}
    assert rc.all_fields.get("author") == "A"
    assert rc.has_done_discovery is True


# ------------------------------------ PipelineStats ------------------------------------- #


def test_pipeline_stats_roundtrip_and_non_negative() -> None:
    stats = PipelineStats(
        total_urls=PIPE_TOTAL,
        succeeded=PIPE_SUCCEEDED,
        failed=PIPE_FAILED,
        duration_sec=PIPE_DURATION,
    )
    assert stats.total_urls == PIPE_TOTAL
    assert stats.succeeded == PIPE_SUCCEEDED
    assert stats.failed == PIPE_FAILED
    assert stats.duration_sec == pytest.approx(PIPE_DURATION)

    # negative should error (validator-specific messages not imported -> use generic match)
    with pytest.raises(ValueError, match=r".*"):
        PipelineStats(total_urls=-1, succeeded=0, failed=0, duration_sec=0.0)
    with pytest.raises(ValueError, match=r".*"):
        PipelineStats(total_urls=1, succeeded=-1, failed=2, duration_sec=0.0)
    with pytest.raises(ValueError, match=r".*"):
        PipelineStats(total_urls=1, succeeded=1, failed=0, duration_sec=-0.1)


# ------------------------------------- ScrapedItem -------------------------------------- #


def test_scraped_item_minimal_and_extra_fields_allowed() -> None:
    item = ScrapedItem(
        url="https://example.com/p",
        title=None,
        description=None,
        price=None,
        author=None,
        date_published=None,
        # extra key should be allowed and preserved
        extra_field="hello",
    )
    assert item.url == "https://example.com/p"
    # Extra fields live in model_extra in pydantic v2
    assert "extra_field" in (item.model_extra or {})
    assert (item.model_extra or {})["extra_field"] == "hello"


def test_scraped_item_price_cleaning_valid() -> None:
    item = ScrapedItem(
        url="https://example.com/p",
        title="T",
        description=None,
        price="$1,299.99",  # should be cleaned to float 1299.99
        author=None,
        date_published=None,
    )
    assert isinstance(item.price, float)
    assert item.price == pytest.approx(1299.99)


def test_scraped_item_price_cleaning_invalid_raises() -> None:
    with pytest.raises(ValidationError) as ei:
        ScrapedItem(
            url="https://example.com/p",
            title="T",
            description=None,
            price="N/A",  # cleaned to empty -> invalid format
            author=None,
            date_published=None,
        )
    assert MSG_ERROR_INVALID_PRICE_FORMAT.format(value="N/A") in str(ei.value)


@pytest.mark.parametrize(
    "field_name",
    ["title", "description", "author", "date_published", "screenshot_path"],
)
def test_scraped_item_optional_string_empty_raises(field_name: str) -> None:
    payload: dict[str, Any] = {
        "url": "https://example.com/p",
        "title": None,
        "description": None,
        "price": None,
        "author": None,
        "date_published": None,
        "screenshot_path": None,
    }
    payload[field_name] = ""  # empty string not allowed for optional fields
    with pytest.raises(ValidationError) as ei:  # expect ValidationError
        ScrapedItem(**payload)
    # Pydantic's str(exception) is a multi-line report; check substring
    assert MSG_ERROR_EMPTY_STRING.format(field=field_name) in str(ei.value)


def test_pipeline_output_with_items() -> None:
    item = ScrapedItem(
        url="https://example.com/p",
        title="Title",
        description="Desc",
        price=None,
        author=None,
        date_published=None,
    )
    stats = PipelineStats(
        total_urls=1,
        succeeded=1,
        failed=0,
        duration_sec=0.01,
    )
    out = PipelineOutput(items=[item], stats=stats)

    assert len(out.items) == 1
    assert out.items[0].title == "Title"
    assert out.stats.succeeded == 1


# ---------------------------------- WorkerPoolConfig ------------------------------------ #


def test_worker_pool_config_defaults_and_customization() -> None:
    # defaults
    cfg = WorkerPoolConfig(take_screenshot=False)
    assert cfg.openai is None
    assert cfg.concurrency == DEFAULT_CONCURRENCY
    assert cfg.max_queue_size is None
    assert cfg.on_item_processed is None
    assert cfg.on_error is None
    assert cfg.on_progress is None
    assert cfg.preserve_order is False
    assert cfg.should_cancel is None

    progress_calls: list[tuple[int, int]] = []

    def on_progress(processed: int, total: int) -> None:
        progress_calls.append((processed, total))

    def should_cancel() -> bool:
        return False

    custom = WorkerPoolConfig(
        take_screenshot=True,
        concurrency=CUSTOM_CONCURRENCY,
        max_queue_size=CUSTOM_MAX_QUEUE,
        on_item_processed=None,
        on_error=None,
        on_progress=on_progress,
        preserve_order=True,
        should_cancel=should_cancel,
    )

    assert custom.take_screenshot is True
    assert custom.concurrency == CUSTOM_CONCURRENCY
    assert custom.max_queue_size == CUSTOM_MAX_QUEUE
    assert custom.preserve_order is True

    # exercise callbacks for signature correctness
    on_progress(1, 5)
    assert progress_calls == [(1, 5)]
    assert should_cancel() is False


def test_worker_pool_config_invalid_numbers_raise_and_zero_allowed() -> None:
    with pytest.raises(ValueError, match=r".*"):
        WorkerPoolConfig(take_screenshot=False, concurrency=0)
    # With the new validator, max_queue_size=0 is valid and means "unbounded"
    cfg = WorkerPoolConfig(take_screenshot=False, max_queue_size=0)
    assert cfg.max_queue_size == 0
    # Negative still invalid
    with pytest.raises(ValueError, match=r".*"):
        WorkerPoolConfig(take_screenshot=False, max_queue_size=-1)


def test_scrape_request_invalid_url_raises() -> None:
    with pytest.raises(ValueError, match=r".*"):
        ScrapeRequest(text="x", url="not-a-url")


def test_scraped_item_invalid_url_raises() -> None:
    with pytest.raises(ValueError, match=r".*"):
        ScrapedItem(
            url="ftp://example.com/p",
            title=None,
            description=None,
            price=None,
            author=None,
            date_published=None,
        )
