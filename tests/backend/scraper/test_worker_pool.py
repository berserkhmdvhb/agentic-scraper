from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any, Protocol, cast

import pytest

from agentic_scraper.backend.scraper import agents as agents_mod
from agentic_scraper.backend.scraper.models import ScrapeRequest, WorkerPoolConfig
from agentic_scraper.backend.scraper.schemas import ScrapedItem
from agentic_scraper.backend.scraper.worker_pool import run_worker_pool

if TYPE_CHECKING:
    # Imported only for typing to satisfy TC001
    from agentic_scraper.backend.core.settings import Settings


# Protocol that matches the real extract_structured_data signature
class Extractor(Protocol):
    def __call__(
        self, request: ScrapeRequest, *, settings: Settings
    ) -> Coroutine[Any, Any, ScrapedItem | None]: ...


@pytest.mark.asyncio
async def test_run_worker_pool_success_basic(settings: Settings) -> None:
    async def fake_extract(_req: ScrapeRequest, *, settings: Settings) -> ScrapedItem:
        _ = settings
        return ScrapedItem(
            url="https://ok",
            title=None,
            description=None,
            price=None,
            author=None,
            date_published=None,
        )

    orig: Extractor = agents_mod.extract_structured_data
    agents_mod.extract_structured_data = cast("Extractor", fake_extract)
    try:
        cfg = WorkerPoolConfig(take_screenshot=False, concurrency=2)
        inputs = [("https://a", "ta"), ("https://b", "tb")]
        out = await run_worker_pool(inputs, settings=settings, config=cfg)

        assert len(out) == len(inputs)
        assert all(isinstance(x, ScrapedItem) for x in out)
    finally:
        agents_mod.extract_structured_data = orig


@pytest.mark.asyncio
async def test_run_worker_pool_preserve_order(settings: Settings) -> None:
    async def fake_extract(req: ScrapeRequest, *, settings: Settings) -> ScrapedItem:
        _ = settings
        # delay based on url to scramble completion
        await asyncio.sleep(0.02 if "1" in req.url else 0.0)
        return ScrapedItem(
            url=req.url,
            title=None,
            description=None,
            price=None,
            author=None,
            date_published=None,
        )

    orig: Extractor = agents_mod.extract_structured_data
    agents_mod.extract_structured_data = cast("Extractor", fake_extract)
    try:
        cfg = WorkerPoolConfig(take_screenshot=False, concurrency=3, preserve_order=True)
        inputs = [("https://x/0", "t0"), ("https://x/1", "t1"), ("https://x/2", "t2")]

        out = await run_worker_pool(inputs, settings=settings, config=cfg)

        # Must be in input order when preserve_order=True
        assert [o.url for o in out] == [u for (u, _t) in inputs]
    finally:
        agents_mod.extract_structured_data = orig


@pytest.mark.asyncio
async def test_run_worker_pool_progress_callbacks(settings: Settings) -> None:
    progress: list[tuple[int, int]] = []

    def on_progress(done: int, total: int) -> None:
        progress.append((done, total))

    async def fake_extract(_req: ScrapeRequest, *, settings: Settings) -> ScrapedItem:
        _ = settings
        await asyncio.sleep(0.001)
        return ScrapedItem(
            url="https://ok",
            title=None,
            description=None,
            price=None,
            author=None,
            date_published=None,
        )

    orig: Extractor = agents_mod.extract_structured_data
    agents_mod.extract_structured_data = cast("Extractor", fake_extract)
    try:
        cfg = WorkerPoolConfig(
            take_screenshot=False,
            concurrency=2,
            on_progress=on_progress,
        )
        inputs = [
            ("https://u1.test", "t1"),
            ("https://u2.test", "t2"),
            ("https://u3.test", "t3"),
        ]

        _ = await run_worker_pool(inputs, settings=settings, config=cfg)

        # Should see initial 0/3 and a final 3/3 (may have intermediate steps)
        assert (0, 3) in progress
        assert (3, 3) in progress
    finally:
        agents_mod.extract_structured_data = orig


@pytest.mark.asyncio
async def test_run_worker_pool_cancel_via_event(settings: Settings) -> None:
    async def fake_extract(_req: ScrapeRequest, *, settings: Settings) -> ScrapedItem:
        _ = settings
        await asyncio.sleep(0.05)  # long work; we will cancel
        return ScrapedItem(
            url="https://ok",
            title=None,
            description=None,
            price=None,
            author=None,
            date_published=None,
        )

    orig: Extractor = agents_mod.extract_structured_data
    agents_mod.extract_structured_data = cast("Extractor", fake_extract)
    try:
        cancel_event = asyncio.Event()
        cancel_event.set()
        cfg = WorkerPoolConfig(take_screenshot=False, concurrency=2)

        out = await run_worker_pool(
            [("https://cancel.test", "t")],
            settings=settings,
            config=cfg,
            cancel_event=cancel_event,
        )

        # Cancel before start -> pool returns quickly with empty results
        assert out == []
    finally:
        agents_mod.extract_structured_data = orig


@pytest.mark.asyncio
async def test_run_worker_pool_error_path_calls_on_error(settings: Settings) -> None:
    errors: list[str] = []

    def on_error(url: str, err: Exception) -> None:
        errors.append(url + ":" + err.__class__.__name__)

    async def fake_extract(_req: ScrapeRequest, *, settings: Settings) -> ScrapedItem:
        _ = settings
        err_msg = "boom"
        raise RuntimeError(err_msg)

    orig: Extractor = agents_mod.extract_structured_data
    agents_mod.extract_structured_data = cast("Extractor", fake_extract)
    try:
        cfg = WorkerPoolConfig(take_screenshot=False, concurrency=1, on_error=on_error)

        out = await run_worker_pool(
            [("https://u.test", "t")],
            settings=settings,
            config=cfg,
        )

        assert out == []
        assert errors
        assert errors[0].startswith("https://u.test:RuntimeError")
    finally:
        agents_mod.extract_structured_data = orig
