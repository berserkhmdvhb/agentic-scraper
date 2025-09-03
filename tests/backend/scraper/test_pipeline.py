from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from agentic_scraper.backend.config.constants import FETCH_ERROR_PREFIX
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.scraper.pipeline import PipelineOptions, scrape_urls, scrape_with_stats
from agentic_scraper.backend.scraper.schemas import ScrapedItem

if TYPE_CHECKING:
    from agentic_scraper.backend.core.settings import Settings

EXPECTED_TWO = 2
EXPECTED_ZERO = 0
EXPECTED_ONE = 1


# --- small helpers to keep tests simple / Ruff-friendly --------------------- #
def _make_hooks_recorder() -> tuple[object, dict[str, object]]:
    calls: dict[str, object] = {
        "started": None,
        "progress": [],
        "processed": [],
        "completed": None,
    }

    class Hooks:
        def on_started(self, n: int) -> None:
            calls["started"] = n

        def on_progress(self, done: int, total: int) -> None:
            progress_list = calls["progress"]
            assert isinstance(progress_list, list)
            progress_list.append((done, total))

        def on_item_processed(self, item: ScrapedItem) -> None:
            processed_list = calls["processed"]
            assert isinstance(processed_list, list)
            processed_list.append(item.url)

        def on_completed(self, *, success: int, failed: int, duration_sec: float) -> None:
            calls["completed"] = (success, failed, duration_sec)

    return Hooks(), calls


async def _fake_run_worker_pool_invoke_hooks(
    *,
    inputs: list[tuple[str, str]],
    settings: Settings,
    config: object,
    cancel_event: object,
    should_cancel: object,
) -> list[ScrapedItem]:
    _ = (inputs, settings, cancel_event, should_cancel)
    on_progress = getattr(config, "on_progress", None)
    on_item_processed = getattr(config, "on_item_processed", None)

    item = ScrapedItem(
        url="https://ok",
        title=None,
        description=None,
        price=None,
        author=None,
        date_published=None,
    )

    if callable(on_progress):
        on_progress(0, 1)
    if callable(on_item_processed):
        on_item_processed(item)
    if callable(on_progress):
        on_progress(1, 1)

    return [item]


# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_scrape_urls_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    urls: list[str] = ["https://a.test", "https://b.test"]

    async def fake_fetch_all(
        *,
        urls: list[str],
        settings: Settings,
        concurrency: int,
        cancel: object,
    ) -> dict[str, str]:
        _ = (urls, settings, concurrency, cancel)
        return {u: f"<html>{u}</html>" for u in urls}

    def fake_extract_main_text(html: str) -> str:
        return f"text:{html}"

    captured_inputs: list[tuple[str, str]] = []

    async def fake_run_worker_pool(
        *,
        inputs: list[tuple[str, str]],
        settings: Settings,
        config: object,
        cancel_event: object,
        should_cancel: object,
    ) -> list[ScrapedItem]:
        _ = (settings, config, cancel_event, should_cancel)
        captured_inputs.extend(inputs)
        return [
            ScrapedItem(
                url=u,
                title=None,
                description=None,
                price=None,
                author=None,
                date_published=None,
            )
            for (u, _t) in inputs
        ]

    # Patch in the pipeline namespace (import site)
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.fetch_all",
        fake_fetch_all,
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.extract_main_text",
        fake_extract_main_text,
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.run_worker_pool",
        fake_run_worker_pool,
        raising=True,
    )

    out = await scrape_urls(
        urls,
        settings=settings,
        openai=None,
        options=PipelineOptions(),
    )

    assert len(out) == EXPECTED_TWO
    assert all(isinstance(x, ScrapedItem) for x in out)
    # Inputs should be (url, extracted_text)
    assert captured_inputs == [(u, f"text:<html>{u}</html>") for u in urls]


@pytest.mark.asyncio
async def test_scrape_urls_filters_fetch_errors(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    urls: list[str] = ["https://ok.test", "https://bad.test"]

    async def fake_fetch_all(
        *,
        urls: list[str],
        settings: Settings,
        concurrency: int,
        cancel: object,
    ) -> dict[str, str]:
        _ = (urls, settings, concurrency, cancel)
        return {
            "https://ok.test": "<html>ok</html>",
            "https://bad.test": f"{FETCH_ERROR_PREFIX} timeout",
        }

    def fake_extract_main_text(html: str) -> str:
        return f"TXT:{html}"

    async def fake_run_worker_pool(
        *,
        inputs: list[tuple[str, str]],
        settings: Settings,
        config: object,
        cancel_event: object,
        should_cancel: object,
    ) -> list[ScrapedItem]:
        _ = (settings, config, cancel_event, should_cancel)
        # Should receive only the OK input
        assert inputs == [("https://ok.test", "TXT:<html>ok</html>")]
        return [
            ScrapedItem(
                url="https://ok.test",
                title=None,
                description=None,
                price=None,
                author=None,
                date_published=None,
            )
        ]

    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.fetch_all",
        fake_fetch_all,
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.extract_main_text",
        fake_extract_main_text,
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.run_worker_pool",
        fake_run_worker_pool,
        raising=True,
    )

    out = await scrape_urls(
        urls,
        settings=settings,
        openai=None,
        options=PipelineOptions(),
    )
    assert len(out) == EXPECTED_ONE
    assert out[0].url == "https://ok.test"


@pytest.mark.asyncio
async def test_scrape_urls_early_cancel_before_start(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    cancel_event = asyncio.Event()
    cancel_event.set()

    # If cancel happens before start, fetch_all must not be called.
    def _should_not_call(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        msg = "fetch_all should not be called when canceled before start"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.fetch_all",
        _should_not_call,
        raising=True,
    )

    out = await scrape_urls(
        ["https://x"],
        settings=settings,
        openai=None,
        options=PipelineOptions(cancel_event=cancel_event),
    )
    assert out == []


@pytest.mark.asyncio
async def test_scrape_urls_cancel_before_worker_pool(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    cancel_event = asyncio.Event()

    async def fake_fetch_all(
        *,
        urls: list[str],
        settings: Settings,
        concurrency: int,
        cancel: object,
    ) -> dict[str, str]:
        _ = (urls, settings, concurrency, cancel)
        # After fetch completes, signal cancellation before worker pool starts
        cancel_event.set()
        return {"https://x": "<html>x</html>"}

    def fake_extract_main_text(html: str) -> str:
        _ = html
        return "text"

    def _run_pool_should_not_be_called(**kwargs: object) -> None:
        _ = kwargs
        msg = "run_worker_pool should not be called when canceled after fetch"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.fetch_all",
        fake_fetch_all,
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.extract_main_text",
        fake_extract_main_text,
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.run_worker_pool",
        _run_pool_should_not_be_called,
        raising=True,
    )

    out = await scrape_urls(
        ["https://x"],
        settings=settings,
        openai=None,
        options=PipelineOptions(cancel_event=cancel_event),
    )
    assert out == []


@pytest.mark.asyncio
async def test_scrape_with_stats_success(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    urls: list[str] = ["https://a", "https://b"]

    async def fake_scrape_urls(
        urls: list[str],
        settings: Settings,
        openai: object | None = None,
        *,
        options: PipelineOptions | None = None,
    ) -> list[ScrapedItem]:
        _ = (urls, settings, openai, options)
        return [
            ScrapedItem(
                url=u,
                title=None,
                description=None,
                price=None,
                author=None,
                date_published=None,
            )
            for u in urls
        ]

    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.scrape_urls",
        fake_scrape_urls,
        raising=True,
    )

    results, stats = await scrape_with_stats(
        urls,
        settings=settings,
        openai=None,
        options=PipelineOptions(),
    )

    assert len(results) == EXPECTED_TWO
    assert stats["num_urls"] == EXPECTED_TWO
    assert stats["num_success"] == EXPECTED_TWO
    assert stats["num_failed"] == EXPECTED_ZERO
    assert stats["was_canceled"] is False
    # duration_sec is a float rounded to 2 decimals
    assert isinstance(stats["duration_sec"], float)


@pytest.mark.asyncio
async def test_scrape_with_stats_canceled_before_start(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    urls: list[str] = ["https://only"]

    cancel_event = asyncio.Event()
    cancel_event.set()

    async def fake_scrape_urls(
        urls: list[str],
        settings: Settings,
        openai: object | None = None,
        *,
        options: PipelineOptions | None = None,
    ) -> list[ScrapedItem]:
        _ = (urls, settings, openai, options)
        # Pipeline should return empty due to cancel
        return []

    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.scrape_urls",
        fake_scrape_urls,
        raising=True,
    )

    results, stats = await scrape_with_stats(
        urls,
        settings=settings,
        openai=None,
        options=PipelineOptions(cancel_event=cancel_event),
    )

    assert results == []
    assert stats["num_urls"] == EXPECTED_ONE
    assert stats["num_success"] == EXPECTED_ZERO
    assert stats["num_failed"] == EXPECTED_ONE
    assert stats["was_canceled"] is True


@pytest.mark.asyncio
async def test_scrape_urls_all_fetch_errors(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    urls: list[str] = ["https://a", "https://b"]

    async def fake_fetch_all(
        *,
        urls: list[str],
        settings: Settings,
        concurrency: int,
        cancel: object,
    ) -> dict[str, str]:
        _ = (urls, settings, concurrency, cancel)
        return dict.fromkeys(urls, f"{FETCH_ERROR_PREFIX} boom")

    def _run_pool_should_not_be_called(**kwargs: object) -> None:
        _ = kwargs
        msg = "run_worker_pool should not be called when there are no valid inputs"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.fetch_all",
        fake_fetch_all,
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.run_worker_pool",
        _run_pool_should_not_be_called,
        raising=True,
    )

    out = await scrape_urls(
        urls,
        settings=settings,
        openai=None,
        options=PipelineOptions(),
    )
    assert out == []


@pytest.mark.asyncio
async def test_scrape_urls_invokes_job_hooks(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    urls: list[str] = ["https://ok"]

    async def fake_fetch_all(
        *,
        urls: list[str],
        settings: Settings,
        concurrency: int,
        cancel: object,
    ) -> dict[str, str]:
        _ = (urls, settings, concurrency, cancel)
        return {"https://ok": "<html/>"}

    def fake_extract_main_text(html: str) -> str:
        _ = html
        return "txt"

    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.fetch_all",
        fake_fetch_all,
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.extract_main_text",
        fake_extract_main_text,
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.run_worker_pool",
        _fake_run_worker_pool_invoke_hooks,
        raising=True,
    )

    hooks, calls = _make_hooks_recorder()

    out = await scrape_with_stats(
        urls,
        settings=settings,
        openai=None,
        options=PipelineOptions(job_hooks=hooks),
    )
    results, stats = out

    assert [r.url for r in results] == ["https://ok"]
    assert calls["started"] == EXPECTED_ONE
    processed_list = calls["processed"]
    assert isinstance(processed_list, list)
    assert processed_list == ["https://ok"]
    completed = calls["completed"]
    assert isinstance(completed, tuple)
    assert completed[0] == EXPECTED_ONE
    assert stats["num_success"] == EXPECTED_ONE


@pytest.mark.asyncio
async def test_scrape_urls_llm_mode_changes_concurrency(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    # Force LLM mode and distinct concurrencies to make the assertion meaningful
    settings.agent_mode = AgentMode.LLM_FIXED
    settings.fetch_concurrency = 2
    settings.llm_concurrency = 5

    async def fake_fetch_all(
        *,
        urls: list[str],
        settings: Settings,
        concurrency: int,
        cancel: object,
    ) -> dict[str, str]:
        _ = (urls, settings, concurrency, cancel)
        return {"https://x": "<html/>"}

    def fake_extract_main_text(html: str) -> str:
        _ = html
        return "txt"

    seen_concurrency: list[int] = []

    async def fake_run_worker_pool(
        *,
        inputs: list[tuple[str, str]],
        settings: Settings,
        config: object,
        cancel_event: object,
        should_cancel: object,
    ) -> list[ScrapedItem]:
        _ = (inputs, settings, cancel_event, should_cancel)
        # capture the concurrency used in pool config
        conc = getattr(config, "concurrency", None)
        assert isinstance(conc, int)
        seen_concurrency.append(conc)
        return [
            ScrapedItem(
                url="https://x",
                title=None,
                description=None,
                price=None,
                author=None,
                date_published=None,
            )
        ]

    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.fetch_all",
        fake_fetch_all,
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.extract_main_text",
        fake_extract_main_text,
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.pipeline.run_worker_pool",
        fake_run_worker_pool,
        raising=True,
    )

    _ = await scrape_urls(
        ["https://x"],
        settings=settings,
        openai=None,
        options=PipelineOptions(),
    )
    assert seen_concurrency == [settings.llm_concurrency]
