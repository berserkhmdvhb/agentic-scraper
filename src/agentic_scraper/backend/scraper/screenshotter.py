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
from agentic_scraper.backend.utils.validators import is_valid_url, validate_path

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """
    Convert a string into a safe, filesystem-friendly slug.

    Non-alphanumeric characters are replaced with dashes, and the result
    is trimmed and truncated to a maximum of 40 characters.

    Args:
        text (str): Input string to sanitize (e.g., domain or page title).

    Returns:
        str: Slugified string safe for use in filenames.
    """
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")[:40]


async def capture_screenshot(url: str, output_dir: Path) -> str | None:
    """
    Capture a full-page screenshot of the given URL using Playwright.

    The output file is named using a combination of the domain slug and
    a short hash of the URL to ensure uniqueness.

    Args:
        url (str): The target URL to capture.
        output_dir (Path): Directory where the screenshot will be saved.

    Returns:
        str | None: Filesystem path to the saved screenshot, or None if capture failed.
    """
    if not is_valid_url(url):
        logger.exception(MSG_ERROR_INVALID_SCREENSHOT_URL.format(url=url))
        return None

    output_path = validate_path(str(output_dir))
    output_path.mkdir(parents=True, exist_ok=True)

    # Use domain for base filename
    domain = urlparse(url).netloc
    base = slugify(domain)

    # Add short hash from URL
    hash_suffix = hashlib.blake2b(url.encode(), digest_size=4).hexdigest()
    filename = f"{base}-{hash_suffix}.png"

    file_path = output_path / filename

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1280, "height": 800})
            await page.goto(url, wait_until="networkidle", timeout=15000)
            await page.screenshot(path=file_path, full_page=True)
            await browser.close()
            logger.info(MSG_INFO_SCREENSHOT_SAVED.format(path=file_path))
            return file_path.as_posix()
    except Exception:
        logger.exception("%s [URL: %s]", MSG_ERROR_SCREENSHOT_FAILED, url)
        return None
