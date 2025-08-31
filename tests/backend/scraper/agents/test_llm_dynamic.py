from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from agentic_scraper.backend.config.types import OpenAIConfig
from agentic_scraper.backend.scraper.agents import llm_dynamic as ld
from agentic_scraper.backend.scraper.models import ScrapeRequest
from agentic_scraper.backend.scraper.schemas import ScrapedItem

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture

    from agentic_scraper.backend.core.settings import Settings


# ------------------------------- fakes -------------------------------- #


class _Msg:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str | None) -> None:
        self.message = _Msg(content)


class _Response:
    def __init__(self, content: str | None) -> None:
        self.choices: list[_Choice] = [_Choice(content)]


class _FakeCompletions:
    def __init__(self, content: str | None) -> None:
        self._content = content

    async def create(
        self,
        *,
        model: str,
        messages: list[dict[str, object]],
        temperature: float,
        max_tokens: int,
    ) -> _Response:
        _ = (model, messages, temperature, max_tokens)
        return _Response(self._content)


class _FakeChat:
    def __init__(self, content: str | None) -> None:
        self.completions = _FakeCompletions(content)


class _FakeAsyncClient:
    """Matches the minimal surface used by llm_dynamic.AsyncOpenAI."""

    def __init__(self, *, api_key: str | None, project: str | None, content: str | None) -> None:
        _ = (api_key, project)
        self.chat = _FakeChat(content)


# ------------------------------ helpers ------------------------------- #


def _mk_request(
    url: str,
    text: str,
    *,
    take_screenshot: bool,
) -> ScrapeRequest:
    cfg = OpenAIConfig(api_key="sk-test", project_id="proj-test")
    return ScrapeRequest(
        url=url,
        text=text,
        take_screenshot=take_screenshot,
        openai=cfg,
    )


# -------------------------------- tests ------------------------------- #


@pytest.mark.asyncio
async def test_extract_structured_data_success_no_screenshot(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    content = (
        '{"url":"https://ok","title":"T","description":null,'
        '"price":null,"author":null,"date_published":null}'
    )

    def _factory(*, api_key: str | None, project: str | None) -> _FakeAsyncClient:
        return _FakeAsyncClient(api_key=api_key, project=project, content=content)

    monkeypatch.setattr(ld, "AsyncOpenAI", _factory, raising=True)

    req = _mk_request(
        url="https://ok",
        text="<html>hello</html>",
        take_screenshot=False,
    )
    out = await ld.extract_structured_data(req, settings=settings)
    assert isinstance(out, ScrapedItem)
    assert out.url == "https://ok"
    assert out.title == "T"


@pytest.mark.asyncio
async def test_extract_structured_data_calls_screenshot_and_sets_path(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    content = (
        '{"url":"https://ok","title":"T","description":null,'
        '"price":null,"author":null,"date_published":null}'
    )

    def _factory(*, api_key: str | None, project: str | None) -> _FakeAsyncClient:
        return _FakeAsyncClient(api_key=api_key, project=project, content=content)

    monkeypatch.setattr(ld, "AsyncOpenAI", _factory, raising=True)

    calls: list[str] = []

    async def _fake_capture(url: str, settings: Settings) -> str | None:
        _ = settings
        calls.append(url)
        return Path("snap.png").as_posix()

    monkeypatch.setattr(ld, "capture_optional_screenshot", _fake_capture, raising=True)

    req = _mk_request(
        url="https://ok",
        text="<html>hello</html>",
        take_screenshot=True,
    )
    out = await ld.extract_structured_data(req, settings=settings)
    assert isinstance(out, ScrapedItem)
    assert calls == ["https://ok"]
    # Dynamic agent attaches screenshot immediately when enabled
    assert getattr(out, "screenshot_path", None) == Path("snap.png").as_posix()


@pytest.mark.asyncio
async def test_extract_structured_data_empty_content_returns_none(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    caplog: LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    caplog.set_level("WARNING", logger="agentic_scraper.backend.scraper.agents.llm_dynamic")

    def _factory(*, api_key: str | None, project: str | None) -> _FakeAsyncClient:
        return _FakeAsyncClient(api_key=api_key, project=project, content=None)

    monkeypatch.setattr(ld, "AsyncOpenAI", _factory, raising=True)

    req = _mk_request(
        url="https://bad",
        text="<html>z</html>",
        take_screenshot=False,
    )
    out = await ld.extract_structured_data(req, settings=settings)
    assert out is None
    # Some setups bypass caplog; stderr is reliable for this logger.
    err_text = capsys.readouterr().err.lower()
    assert "empty" in err_text or "response was none" in err_text


@pytest.mark.asyncio
async def test_extract_structured_data_handles_openai_exception(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    """When the client raises an OpenAI-style error, the helper should handle and return None."""

    class _BoomError(Exception):
        pass

    class _RaisingCompletions:
        async def create(
            self,
            *,
            model: str,
            messages: list[dict[str, object]],
            temperature: float,
            max_tokens: int,
        ) -> _Response:
            _ = (model, messages, temperature, max_tokens)
            msg = "boom"
            raise _BoomError(msg)

    class _RaisingChat:
        def __init__(self) -> None:
            self.completions = _RaisingCompletions()

    class _Client:
        def __init__(self, *, api_key: str | None, project: str | None) -> None:
            _ = (api_key, project)
            self.chat = _RaisingChat()

    # Treat _BoomError as an OpenAIErrorT for the except clause in llm_dynamic
    monkeypatch.setattr(ld, "OpenAIErrorT", _BoomError, raising=True)
    monkeypatch.setattr(ld, "AsyncOpenAI", _Client, raising=True)

    handled: list[str] = []

    def _spy_handle(e: BaseException, *, url: str, settings: Settings) -> None:
        _ = (url, settings)
        handled.append(e.__class__.__name__)

    monkeypatch.setattr(ld, "handle_openai_exception", _spy_handle, raising=True)

    req = _mk_request(
        url="https://err",
        text="<html>oops</html>",
        take_screenshot=False,
    )
    out = await ld.extract_structured_data(req, settings=settings)
    assert out is None
    assert handled == ["_BoomError"]
