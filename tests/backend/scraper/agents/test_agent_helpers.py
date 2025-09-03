from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from agentic_scraper.backend.config.types import OpenAIConfig
from agentic_scraper.backend.scraper.agents import agent_helpers as ah
from agentic_scraper.backend.scraper.schemas import ScrapedItem

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture

    from agentic_scraper.backend.config.aliases import OpenAIErrorT
    from agentic_scraper.backend.core.settings import Settings


# ------------------------------ parse_llm_response ------------------------------ #


def test_parse_llm_response_repairs_simple_issues_verbose(settings: Settings) -> None:
    settings.verbose = True  # enable verbose path
    bad = """
    ```json
    {'url':'https://x','title':'T',}
    ```
    """.strip()

    parsed = ah.parse_llm_response(bad, url="https://x", settings=settings)
    assert parsed is not None
    assert parsed.get("url") == "https://x"
    assert parsed.get("title") == "T"


# ------------------------------ capture_optional_screenshot ------------------------------ #


@pytest.mark.asyncio
async def test_capture_optional_screenshot_success(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    tmp_path: Path,
) -> None:
    settings.screenshot_dir = str(tmp_path)

    async def _fake_capture(url: str, *, output_dir: Path) -> str:
        _ = (url, output_dir)
        return (tmp_path / "ok.png").as_posix()

    monkeypatch.setattr(ah, "capture_screenshot", _fake_capture, raising=True)

    out = await ah.capture_optional_screenshot("https://x", settings=settings)
    assert isinstance(out, str)
    assert out.endswith("ok.png")


@pytest.mark.asyncio
async def test_capture_optional_screenshot_failure_logs(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    caplog: LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Capture warnings from the agent_helpers module logger
    caplog.set_level(
        "WARNING",
        logger="agentic_scraper.backend.scraper.agents.agent_helpers",
    )

    async def _boom(url: str, *, output_dir: Path) -> str:
        _ = (url, output_dir)
        msg = "bad"
        raise ValueError(msg)

    monkeypatch.setattr(ah, "capture_screenshot", _boom, raising=True)

    out = await ah.capture_optional_screenshot("https://x", settings=settings)
    assert out is None
    # Stderr assertion is robust across handler setups
    stderr = capsys.readouterr().err.lower()
    assert "failed to capture screenshot" in stderr


# ------------------------------ handle_openai_exception ------------------------------ #
# Spy on module logger instead of relying on caplog handler plumbing.
# Cast test exceptions to the shared alias type so mypy is satisfied.


def test_handle_openai_exception_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    class _FakeRateLimitError(Exception):
        pass

    class _FakeAPIError(Exception):
        pass

    # Patch names so isinstance checks match inside agent_helpers
    monkeypatch.setattr(ah, "RateLimitErrorT", _FakeRateLimitError, raising=True)
    monkeypatch.setattr(ah, "APIErrorT", _FakeAPIError, raising=True)

    seen: list[str] = []

    def _spy_warning(msg: str, *_args: object, **_kwargs: object) -> None:
        seen.append(str(msg))

    monkeypatch.setattr(ah.logger, "warning", _spy_warning, raising=True)

    err = cast("OpenAIErrorT", _FakeRateLimitError("x"))
    ah.handle_openai_exception(err, url="https://x", settings=settings)
    assert any("rate limit" in m.lower() for m in seen)


def test_handle_openai_exception_apierror(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    class _FakeRateLimitError(Exception):
        pass

    class _FakeAPIError(Exception):
        pass

    monkeypatch.setattr(ah, "RateLimitErrorT", _FakeRateLimitError, raising=True)
    monkeypatch.setattr(ah, "APIErrorT", _FakeAPIError, raising=True)

    seen: list[str] = []

    def _spy_warning(msg: str, *_args: object, **_kwargs: object) -> None:
        seen.append(str(msg))

    monkeypatch.setattr(ah.logger, "warning", _spy_warning, raising=True)

    err = cast("OpenAIErrorT", _FakeAPIError("boom"))
    ah.handle_openai_exception(err, url="https://x", settings=settings)
    assert any("api" in m.lower() or "error" in m.lower() for m in seen)


def test_handle_openai_exception_unexpected(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    class _SomethingElseError(Exception):
        pass

    # Ensure it doesn't match patched RL/API types
    monkeypatch.setattr(ah, "RateLimitErrorT", type("X", (Exception,), {}), raising=True)
    monkeypatch.setattr(ah, "APIErrorT", type("Y", (Exception,), {}), raising=True)

    seen: list[str] = []

    def _spy_warning(msg: str, *_args: object, **_kwargs: object) -> None:
        seen.append(str(msg))

    monkeypatch.setattr(ah.logger, "warning", _spy_warning, raising=True)

    err = cast("OpenAIErrorT", _SomethingElseError("what"))
    ah.handle_openai_exception(err, url="https://x", settings=settings)
    assert any("unexpected" in m.lower() or "openai" in m.lower() for m in seen)


# ------------------------------ log_structured_data ------------------------------ #


def test_log_structured_data_verbose_dump(
    settings: Settings,
    tmp_path: Path,
) -> None:
    settings.verbose = True
    settings.dump_llm_json_dir = str(tmp_path)

    data = {"url": "https://x", "title": "T", "description": None}
    ah.log_structured_data(data, settings=settings)

    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    loaded = json.loads(files[0].read_text(encoding="utf-8"))
    assert loaded["url"] == "https://x"


def test_log_structured_data_non_verbose_noop(
    settings: Settings,
    tmp_path: Path,
) -> None:
    settings.verbose = False
    settings.dump_llm_json_dir = str(tmp_path)

    data = {"url": "https://x"}
    ah.log_structured_data(data, settings=settings)

    files = list(tmp_path.glob("*.json"))
    assert files == []


# ------------------------------ extract_context_hints ------------------------------ #


def test_extract_context_hints_basic() -> None:
    html = """
    <html>
      <head>
        <title>Widget 1 - Shop</title>
        <meta name="description" content="Great widget." />
        <meta property="og:title" content="Widget 1" />
      </head>
      <body>
        <nav aria-label="breadcrumb">Home > Products > Widget 1</nav>
        <h1>Widget 1</h1>
      </body>
    </html>
    """.strip()

    hints = ah.extract_context_hints(
        html,
        "https://shop.example.com/products/widget-1",
    )

    required = {
        "meta",
        "breadcrumbs",
        "url_segments",
        "context_domain",
        "url_last_segment",
        "page_title",
        "first_h1",
        "page",
    }
    for key in required:
        assert key in hints
    assert hints["page"] in {"product", "job", "blog", "unknown"}


# ------------------------------ try_validate_scraped_item ------------------------------ #


def test_try_validate_scraped_item_success(settings: Settings) -> None:
    data = {
        "url": "https://x",
        "title": None,
        "description": None,
        "price": None,
        "author": None,
        "date_published": None,
    }
    out = ah.try_validate_scraped_item(data, url="https://x", settings=settings)
    assert isinstance(out, ScrapedItem)


def test_try_validate_scraped_item_validation_error(settings: Settings) -> None:
    out = ah.try_validate_scraped_item(
        {"title": "missing url"},
        url="https://x",
        settings=settings,
    )
    assert out is None


# ------------------------------ score_and_log_fields ------------------------------ #


def test_score_and_log_fields_with_raw_data() -> None:
    raw = {"title": "T", "description": "", "price": None, "author": "A"}
    score = ah.score_and_log_fields(set(raw), attempt=1, url="https://x", raw_data=raw)
    assert 0.0 <= score <= 1.0


def test_score_and_log_fields_without_raw_data() -> None:
    fields = {"title", "author"}
    score = ah.score_and_log_fields(fields, attempt=2, url="https://x", raw_data=None)
    assert 0.0 <= score <= 1.0


# ------------------------------ retrieve_openai_credentials ------------------------------ #


def test_retrieve_openai_credentials_success() -> None:
    cfg = OpenAIConfig(api_key="sk-abc", project_id="proj")
    api_key, project = ah.retrieve_openai_credentials(cfg)
    assert api_key == "sk-abc"
    assert project == "proj"


def test_retrieve_openai_credentials_missing_config() -> None:
    with pytest.raises(ValueError, match=r"(?i)missing OpenAI config"):
        _ = ah.retrieve_openai_credentials(None)


def test_retrieve_openai_credentials_missing_fields() -> None:
    with pytest.raises(ValueError, match=r"(?i)missing OpenAI API key"):
        _ = ah.retrieve_openai_credentials(OpenAIConfig(api_key="", project_id="p"))

    # masked key
    with pytest.raises(ValueError, match=r"(?i)masked"):
        _ = ah.retrieve_openai_credentials(OpenAIConfig(api_key="*****", project_id="p"))

    with pytest.raises(ValueError, match=r"(?i)missing OpenAI project"):
        _ = ah.retrieve_openai_credentials(
            OpenAIConfig(api_key="sk-abc", project_id=""),
        )


# ------------------------------ should_exit_early ------------------------------ #


def _mk_item(url: str) -> ScrapedItem:
    return ScrapedItem(
        url=url,
        title=None,
        description=None,
        price=None,
        author=None,
        date_published=None,
    )


def test_should_exit_early_no_item() -> None:
    result = ah.should_exit_early(
        item=None,
        raw_data={},
        best_fields=None,
        missing=set(),
        url="https://x",
    )
    assert result is False


def test_should_exit_early_first_result_always_retry() -> None:
    item = _mk_item("https://x")
    result = ah.should_exit_early(
        item=item,
        raw_data={"title": "T"},
        best_fields=None,
        missing=set(),
        url="https://x",
    )
    assert result is False


def test_should_exit_early_stops_when_no_progress() -> None:
    item = _mk_item("https://x")
    result = ah.should_exit_early(
        item=item,
        raw_data={"title": "T"},
        best_fields={"title": "T"},
        missing=set(),
        url="https://x",
    )
    assert result is True


def test_should_exit_early_continues_when_new_or_filled_missing() -> None:
    item = _mk_item("https://x")

    # New field discovered
    res1 = ah.should_exit_early(
        item=item,
        raw_data={"title": "T", "author": "A"},
        best_fields={"title": "T"},
        missing=set(),
        url="https://x",
    )
    assert res1 is False

    # Previously missing field was filled
    res2 = ah.should_exit_early(
        item=item,
        raw_data={"title": "T"},
        best_fields={"author": None},
        missing={"title"},
        url="https://x",
    )
    assert res2 is False
