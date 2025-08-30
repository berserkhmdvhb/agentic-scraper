from __future__ import annotations

import hashlib
from pathlib import Path
from types import TracebackType

import pytest

from agentic_scraper.backend.scraper.screenshotter import capture_screenshot, slugify

LEN_LONG_TEXT = 40


# -------------------- minimal async Playwright fakes -------------------- #
class _FakePage:
    async def set_viewport_size(self, _size: dict[str, int]) -> None:
        return None

    async def goto(self, _url: str, *, wait_until: str, timeout: int) -> None:
        _ = (wait_until, timeout)

    async def screenshot(self, *, path: Path, full_page: bool) -> None:
        _ = full_page
        # Create a tiny file to assert existence
        path.write_bytes(b"\x89PNG\r\n")


class _FakeBrowser:
    async def new_page(self) -> _FakePage:
        return _FakePage()

    async def close(self) -> None:
        return None


class _FakeChromium:
    async def launch(self, *, headless: bool) -> _FakeBrowser:
        _ = headless
        return _FakeBrowser()


class _FakePlaywright:
    def __init__(self) -> None:
        self.chromium = _FakeChromium()


class _AsyncPWCtx:
    async def __aenter__(self) -> _FakePlaywright:
        return _FakePlaywright()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        _ = (exc_type, exc, tb)


def _fake_async_playwright() -> _AsyncPWCtx:
    return _AsyncPWCtx()


# --------------------------------- tests -------------------------------- #
def test_slugify() -> None:
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("a  b__c") == "a-b-c"
    long_text = "X" * 100
    assert len(slugify(long_text)) == LEN_LONG_TEXT


@pytest.mark.asyncio
async def test_capture_screenshot_invalid_url_logs_and_returns_none(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Patch async_playwright defensively (shouldn't be called on invalid URL)
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.screenshotter.async_playwright",
        _fake_async_playwright,
        raising=True,
    )

    # Patch the module logger to capture exception messages
    captured: list[str] = []

    def _fake_exception(msg: str, *args: object) -> None:
        # mimic logging interpolation
        captured.append(msg % args if args else msg)

    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.screenshotter.logger.exception",
        _fake_exception,
        raising=True,
    )

    out = await capture_screenshot("not-a-url", tmp_path)
    assert out is None

    # Ensure an error mentioning invalid URL was logged
    assert any("Invalid URL" in m for m in captured)


@pytest.mark.asyncio
async def test_capture_screenshot_success_creates_expected_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.screenshotter.async_playwright",
        _fake_async_playwright,
        raising=True,
    )

    url = "https://example.com/some/page"
    expected_slug = slugify("example.com")
    expected_hash = hashlib.blake2b(url.encode(), digest_size=4).hexdigest()

    out = await capture_screenshot(url, tmp_path)
    assert out is not None

    out_path = Path(out)
    assert out_path.exists()
    assert out_path.parent.resolve() == tmp_path.resolve()
    assert out_path.name == f"{expected_slug}-{expected_hash}.png"


@pytest.mark.asyncio
async def test_capture_screenshot_playwright_error_logs_and_returns_none(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Make goto raise to exercise the exception branch
    class _BadPage(_FakePage):
        async def goto(self, _url: str, *, wait_until: str, timeout: int) -> None:
            _ = (wait_until, timeout)
            msg = "boom"
            raise RuntimeError(msg)

    class _BadBrowser(_FakeBrowser):
        async def new_page(self) -> _BadPage:
            return _BadPage()

    class _BadChromium(_FakeChromium):
        async def launch(self, *, headless: bool) -> _BadBrowser:
            _ = headless
            return _BadBrowser()

    class _BadPlaywright(_FakePlaywright):
        def __init__(self) -> None:
            self.chromium = _BadChromium()

    class _BadCtx(_AsyncPWCtx):
        async def __aenter__(self) -> _BadPlaywright:
            return _BadPlaywright()

    def _bad_async_playwright() -> _BadCtx:
        return _BadCtx()

    # Patch playwright to our failing double
    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.screenshotter.async_playwright",
        _bad_async_playwright,
        raising=True,
    )

    # Patch the module logger to capture exception messages
    captured: list[str] = []

    def _fake_exception(msg: str, *args: object) -> None:
        captured.append(msg % args if args else msg)

    monkeypatch.setattr(
        "agentic_scraper.backend.scraper.screenshotter.logger.exception",
        _fake_exception,
        raising=True,
    )

    out = await capture_screenshot("https://example.org", tmp_path)
    assert out is None

    # Ensure the "screenshot failed" message was logged
    assert any("Failed to capture screenshot" in m for m in captured)
