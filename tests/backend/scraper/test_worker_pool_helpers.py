from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any, Callable, cast

import pytest

from agentic_scraper.backend.config.messages import (
    MSG_WARNING_ON_ERROR_CALLBACK_FAILED,
    MSG_WARNING_ON_ITEM_PROCESSED_FAILED,
    MSG_WARNING_PROGRESS_CALLBACK_FAILED,
    MSG_DEBUG_WORKER_PICKED_URL,
    MSG_WARNING_WORKER_FAILED_SHORT,
)
from agentic_scraper.backend.config.types import OpenAIConfig
from agentic_scraper.backend.scraper import worker_pool_helpers as helpers
from agentic_scraper.backend.scraper.models import ScrapeRequest
from agentic_scraper.backend.scraper.schemas import ScrapedItem


@pytest.mark.asyncio
async def test_dequeue_next_logs_pick(monkeypatch: pytest.MonkeyPatch) -> None:
    q: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    await q.put(("https://x", "text"))
    # Stub the module logger to capture the debug message deterministically
    seen: list[str] = []
    def fake_debug(msg: str, *args: object, **kwargs: object) -> None:
        seen.append(msg if not args else msg % args)
    monkeypatch.setattr(helpers.logger, "debug", fake_debug, raising=True)
    url, text = await helpers.dequeue_next(q, worker_id=1)
    assert url == "https://x"
    assert text == "text"
    # Check for the message prefix (avoid format differences)
    prefix = MSG_DEBUG_WORKER_PICKED_URL.split("{", 1)[0]
    assert any(m.startswith(prefix) for m in seen)


def test_build_request_includes_openai_and_logs() -> None:
    req = helpers.build_request(
        scrape_input=("https://ex", "body"),
        take_screenshot=True,
        openai=OpenAIConfig(api_key="k", project_id="p"),
        worker_id=2,
        scrape_request_cls=ScrapeRequest,
    )
    assert isinstance(req, ScrapeRequest)
    assert req.url == "https://ex"
    assert req.text == "body"
    assert req.take_screenshot is True
    assert req.openai is not None


def test_handle_success_item_appends_and_calls_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Minimal fake _WorkerContext
    class _Ctx:
        def __init__(self) -> None:
            self.settings = cast("Any", type("S", (), {"is_verbose_mode": True})())
            self.on_item_processed: Callable[[Any], None] | None = None

    collected: list[ScrapedItem] = []
    ctx = _Ctx()
    calls: list[ScrapedItem] = []

    def on_processed(item: ScrapedItem) -> None:
        calls.append(item)

    ctx.on_item_processed = on_processed

    item = ScrapedItem(
        url="https://x",
        title=None,
        description=None,
        price=None,
        author=None,
        date_published=None,
    )
    helpers.handle_success_item(
        item=item,
        results=collected,
        url="https://x",
        worker_id=1,
        context=cast("Any", ctx),
    )
    assert collected == [item]
    assert calls == [item]


def test_handle_success_item_no_item_logs_no_item() -> None:
    class _Ctx:
        def __init__(self) -> None:
            self.settings = cast("Any", type("S", (), {"is_verbose_mode": True})())
            self.on_item_processed = None

    out: list[ScrapedItem] = []
    helpers.handle_success_item(
        item=None,
        results=out,
        url="https://x",
        worker_id=1,
        context=cast("Any", _Ctx()),
    )
    assert out == []  # nothing appended


def test_handle_success_item_callback_failure_is_guarded(
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture
) -> None:
    class _Ctx:
        def __init__(self) -> None:
            self.settings = cast("Any", type("S", (), {"is_verbose_mode": True})())
            self.on_item_processed = lambda _i: (_ for _ in ()).throw(RuntimeError("boom"))

    # Capture warnings deterministically by stubbing the module logger
    seen: list[str] = []
    def fake_warning(msg: str, *args: object, **kwargs: object) -> None:
        seen.append(msg if not args else msg % args)
    monkeypatch.setattr(helpers.logger, "warning", fake_warning, raising=True)
    out: list[ScrapedItem] = []
    helpers.handle_success_item(
        item=ScrapedItem(
            url="https://x",
            title=None,
            description=None,
            price=None,
            author=None,
            date_published=None,
        ),
        results=out,
        url="https://x",
        worker_id=1,
        context=cast("Any", _Ctx()),
    )
    # Still appended, warning logged
    assert out and out[0].url == "https://x"
    prefix = MSG_WARNING_ON_ITEM_PROCESSED_FAILED.split("{", 1)[0]
    assert any(m.startswith(prefix) or prefix in m for m in seen)


def test_handle_failure_warning_and_callback_guarded(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    class _Ctx:
        def __init__(self) -> None:
            self.settings = cast("Any", type("S", (), {"is_verbose_mode": False})())
            self.on_error = lambda _url, _err: (_ for _ in ()).throw(RuntimeError("cb-err"))

    # Capture warnings deterministically by stubbing the module logger
    seen: list[str] = []
    def fake_warning(msg: str, *args: object, **kwargs: object) -> None:
        seen.append(msg if not args else msg % args)
    monkeypatch.setattr(helpers.logger, "warning", fake_warning, raising=True)
    helpers.handle_failure(
        url="https://bad",
        error=ValueError("x"),
        context=cast("Any", _Ctx()),
    )
    # short warning + callback failure warning
    short_prefix = MSG_WARNING_WORKER_FAILED_SHORT.split("{", 1)[0]
    cb_prefix = MSG_WARNING_ON_ERROR_CALLBACK_FAILED.split("{", 1)[0]
    assert any(m.startswith(short_prefix) or short_prefix in m for m in seen)
    assert any(m.startswith(cb_prefix) or cb_prefix in m for m in seen)

def test_log_progress_verbose_only_when_verbose(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Ctx:
        def __init__(self) -> None:
            self.settings = cast("Any", type("S", (), {"is_verbose_mode": True})())

    # Stub the module logger's debug to avoid caplog handler/propagation differences
    seen: list[str] = []
    def fake_debug(msg: str, *args: object, **kwargs: object) -> None:
        seen.append(msg if not args else msg % args)
    monkeypatch.setattr(helpers.logger, "debug", fake_debug, raising=True)
    q: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    helpers.log_progress_verbose(worker_id=1, url="https://x", queue=q, context=cast("Any", _Ctx()))
    assert any("remaining" in m.lower() for m in seen)


def test_call_progress_callback_happy_and_guarded(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # happy path
    class _Ctx1:
        def __init__(self) -> None:
            self.processed_count = 5
            self.total_inputs = 10
            self.on_progress = lambda p, t: None

    helpers.call_progress_callback(context=cast("Any", _Ctx1()))

    # guarded-path (callback raises)
    class _Ctx2:
        def __init__(self) -> None:
            self.processed_count = 5
            self.total_inputs = 10
            self.on_progress = lambda _p, _t: (_ for _ in ()).throw(RuntimeError("pbooom"))

    # Stub logger.warning to capture the emitted message reliably
    seen: list[str] = []
    def fake_warning(msg: str, *args: object, **kwargs: object) -> None:
        seen.append(msg if not args else msg % args)
    monkeypatch.setattr(helpers.logger, "warning", fake_warning, raising=True)

    helpers.call_progress_callback(context=cast("Any", _Ctx2()))
    prefix = MSG_WARNING_PROGRESS_CALLBACK_FAILED.split("{", 1)[0]
    assert any(prefix in m for m in seen)

@pytest.mark.asyncio
async def test_place_ordered_result_places_by_first_index() -> None:
    # Minimal context with ordering enabled
    class _Ctx:
        def __init__(self) -> None:
            self.preserve_order = True
            self.ordered_results: list[ScrapedItem | None] = [None, None, None]
            self.url_to_indices: dict[str, deque[int]] = {"u": deque([1, 2])}
            self.order_lock = asyncio.Lock()

    ctx = _Ctx()
    item = ScrapedItem(
        url="https://u",
        title=None,
        description=None,
        price=None,
        author=None,
        date_published=None,
    )
    ok1 = await helpers.place_ordered_result(context=cast("Any", ctx), url="u", item=item)
    ok2 = await helpers.place_ordered_result(context=cast("Any", ctx), url="u", item=item)
    assert ok1 and ok2
    assert [r.url if r else None for r in ctx.ordered_results] == [None, "https://u", "https://u"]
