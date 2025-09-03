from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from agentic_scraper.backend.scraper.agents import llm_dynamic_adaptive as lda
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
        messages: list[dict[str, object]] | list[object],
        temperature: float,
        max_tokens: int,
    ) -> _Response:
        _ = (model, messages, temperature, max_tokens)
        return _Response(self._content)


class _FakeChat:
    def __init__(self, content: str | None) -> None:
        self.completions = _FakeCompletions(content)


class _FakeAsyncClient:
    """Matches the minimal surface used by lda.AsyncOpenAI (structural typing)."""

    def __init__(self, *, api_key: str | None, project: str | None, content: str | None) -> None:
        _ = (api_key, project)
        self.chat = _FakeChat(content)


def _mk_request(url: str, html: str) -> ScrapeRequest:
    # We patch `retrieve_openai_credentials` in each test, so `openai=None` is OK.
    return ScrapeRequest(url=url, text=html, take_screenshot=False, openai=None)


# -------------------------------- tests ------------------------------- #


@pytest.mark.asyncio
async def test_adaptive_success_basic(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    """
    Happy-path:
        valid JSON, no screenshot path expected (screenshot is only attached in fallback).
    """
    content = (
        '{"url":"https://ok","title":"T","description":null,'
        '"price":null,"author":null,"date_published":null}'
    )

    # Use a factory so we can pass the model's ctor (api_key, project)
    def _factory(*, api_key: str | None, project: str | None) -> _FakeAsyncClient:
        return _FakeAsyncClient(api_key=api_key, project=project, content=content)

    monkeypatch.setattr(lda, "AsyncOpenAI", _factory, raising=True)
    monkeypatch.setattr(lda, "retrieve_openai_credentials", lambda _cfg: ("k", "p"), raising=True)

    req = _mk_request("https://ok", "<html>hello</html>")
    out = await lda.extract_adaptive_data(req, settings=settings)
    assert isinstance(out, ScrapedItem)
    assert out.url == "https://ok"
    assert out.title == "T"


@pytest.mark.asyncio
async def test_adaptive_empty_content_triggers_fallback_and_logs_warning(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    caplog: LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """If all attempts return empty content, we fall back and log a warning."""
    caplog.set_level(
        "WARNING",
        logger="agentic_scraper.backend.scraper.agents.llm_dynamic_adaptive",
    )

    def _factory(*, api_key: str | None, project: str | None) -> _FakeAsyncClient:
        return _FakeAsyncClient(api_key=api_key, project=project, content=None)

    monkeypatch.setattr(lda, "AsyncOpenAI", _factory, raising=True)
    monkeypatch.setattr(lda, "retrieve_openai_credentials", lambda _cfg: ("k", "p"), raising=True)

    req = _mk_request("https://bad", "<html>z</html>")
    out = await lda.extract_adaptive_data(req, settings=settings)
    assert out is None
    # The module logs MSG_WARN_ADAPTIVE_EXTRACTION_FAILED_AFTER_RETRIES on final fallback.
    # Some setups bypass caplog; stderr is reliable for this logger.
    err_text = capsys.readouterr().err.lower()
    assert (
        ("failed to extract" in err_text) or ("failed after" in err_text) or ("failed" in err_text)
    )


@pytest.mark.asyncio
async def test_adaptive_handles_openai_exception(
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
            messages: list[dict[str, object]] | list[object],
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

    # Treat _BoomError as an OpenAIErrorT for the module's except tuple
    monkeypatch.setattr(lda, "OpenAIErrorT", _BoomError, raising=True)
    monkeypatch.setattr(lda, "AsyncOpenAI", _Client, raising=True)
    monkeypatch.setattr(lda, "retrieve_openai_credentials", lambda _cfg: ("k", "p"), raising=True)

    handled: list[str] = []

    def _spy_handle(e: BaseException, *, url: str, settings: Settings) -> None:
        _ = (url, settings)
        handled.append(e.__class__.__name__)

    monkeypatch.setattr(lda, "handle_openai_exception", _spy_handle, raising=True)

    req = _mk_request("https://err", "<html>oops</html>")
    out = await lda.extract_adaptive_data(req, settings=settings)
    assert out is None
    assert handled == ["_BoomError"]
