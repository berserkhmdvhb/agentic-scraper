import hashlib
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_SCREENSHOT_FAILED,
    MSG_INFO_SCREENSHOT_SAVED,
)

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Sanitize string for safe filename."""
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")[:40]


async def capture_screenshot(url: str, output_dir: Path) -> str | None:
    """
    Captures a full-page screenshot of the given URL and saves it in the output directory.

    Args:
        url (str): The URL to capture.
        output_dir (Path): The directory to save the screenshot in.

    Returns:
        str | None: Path to the saved screenshot, or None if failed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use title or fallback to domain
    domain = urlparse(url).netloc
    base = slugify(domain)

    # Add short hash from URL
    hash_suffix = hashlib.blake2b(url.encode(), digest_size=4).hexdigest()
    filename = f"{base}-{hash_suffix}.png"

    file_path = output_dir / filename

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1280, "height": 800})
            await page.goto(url, wait_until="networkidle", timeout=15000)
            await page.screenshot(path=file_path, full_page=True)
            await browser.close()
            logger.info(MSG_INFO_SCREENSHOT_SAVED, file_path)
            return file_path.as_posix()
    except Exception:
        logger.exception("%s: %s", MSG_ERROR_SCREENSHOT_FAILED, url)
        return None
