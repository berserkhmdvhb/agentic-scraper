"""
Full-page screenshot utility using Playwright.

Responsibilities:
- Validate and normalize target URLs and output directories.
- Generate stable, filesystem-safe filenames (slug + short hash).
- Capture full-page screenshots via headless Chromium.

Public API:
- `slugify`: Convert arbitrary text to a filesystem-safe slug.
- `capture_screenshot`: Save a full-page screenshot for a given URL.

Operational:
- Concurrency: Safe for concurrent calls; each call launches its own browser.
- Retries: None at this layer (delegate to caller if needed).
- Logging: Errors and save confirmations logged via structured messages.

Usage:
    from pathlib import Path
    from agentic_scraper.backend.scraper.screenshotter import capture_screenshot

    path = await capture_screenshot("https://example.com", Path("./screens"))
    if path:
        print("Saved at:", path)

Notes:
- Filenames include a short BLAKE2b hash of the URL to avoid collisions when
  different pages share the same domain.
- The function returns `None` on validation or runtime failure (non-exception control flow).
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_INVALID_SCREENSHOT_URL,
    MSG_ERROR_SCREENSHOT_FAILED,
    MSG_INFO_SCREENSHOT_SAVED,
)
from agentic_scraper.backend.utils.validators import validate_path, validate_url

logger = logging.getLogger(__name__)

__all__ = ["capture_screenshot", "slugify"]


def slugify(text: str) -> str:
    """
    Convert an arbitrary string into a safe, filesystem-friendly slug.

    Non-alphanumeric characters are replaced with dashes, and the result is
    trimmed and truncated to a maximum of 40 characters to keep filenames short.

    Args:
        text (str): Input text (e.g., domain or page title).

    Returns:
        str: Lowercased, dash-separated slug suitable for filenames.

    Examples:
        >>> slugify("Hello, World! 2025 🚀")
        'hello-world-2025'

    Notes:
        - We intentionally limit to 40 chars to avoid excessively long paths on
          some filesystems while keeping filenames readable.
    """
    # Replace any run of non-alnum chars with a single dash; trim; cap length.
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")[:40]


async def capture_screenshot(url: str, output_dir: Path) -> str | None:
    """
    Capture a full-page screenshot using Playwright (headless Chromium).

    The output filename is derived from the URL's domain slug plus a short
    BLAKE2b hash of the full URL to ensure uniqueness across different pages.

    Args:
        url (str): Target page URL (must be http/https).
        output_dir (Path): Directory where the PNG will be saved. Created if missing.

    Returns:
        str | None: Absolute path (as POSIX string) to the saved screenshot, or `None`
            if validation or capture fails.

    Raises:
        None: This function handles errors internally and returns `None` on failure.

    Examples:
        >>> from pathlib import Path
        >>> path = await capture_screenshot("https://example.com/a", Path("./shots"))
        >>> bool(path)
        True

    Notes:
        - We wait for `"networkidle"` to capture a more stable page. This is a
          heuristic and can be adjusted by callers if needed.
        - A fixed viewport is set before navigation; `full_page=True` then expands
          the capture to the full scroll height.
        - Errors are logged with standardized messages; secrets/URLs are not mutated.
    """
    try:
        # Normalize and validate URL early (trims whitespace; enforces http(s)).
        url = validate_url(url)
    except ValueError:
        # Validation errors are not re-raised — callers get `None` but logs contain context.
        logger.exception(MSG_ERROR_INVALID_SCREENSHOT_URL.format(url=url))
        return None

    # Ensure output directory exists (idempotent) and is a valid path.
    output_path = validate_path(str(output_dir))
    output_path.mkdir(parents=True, exist_ok=True)

    # ---- Filename strategy ----------------------------------------------------
    # Base filename uses the domain (readable); add a short URL hash to avoid collisions
    # when multiple pages share a domain or when slugs truncate similarly.
    domain = urlparse(url).netloc
    base = slugify(domain)
    hash_suffix = hashlib.blake2b(url.encode(), digest_size=4).hexdigest()  # 8 hex chars
    filename = f"{base}-{hash_suffix}.png"
    file_path = output_path / filename

    try:
        # Each call uses its own browser context to avoid cross-call state or races.
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Set a deterministic viewport for consistent rendering of responsive pages.
            await page.set_viewport_size({"width": 1280, "height": 800})

            # Navigate and wait for network to be idle to reduce flicker/partial loads.
            await page.goto(url, wait_until="networkidle", timeout=15000)

            # Capture full page (beyond the viewport height).
            await page.screenshot(path=file_path, full_page=True)

            # Clean shutdown to free resources immediately.
            await browser.close()

            logger.info(MSG_INFO_SCREENSHOT_SAVED.format(path=file_path))
            return file_path.as_posix()

    except Exception:
        # Catch-all: Playwright may raise various navigation/rendering errors.
        # We log and return `None` to keep the scraper resilient.
        logger.exception(MSG_ERROR_SCREENSHOT_FAILED.format(url=url))
        return None
