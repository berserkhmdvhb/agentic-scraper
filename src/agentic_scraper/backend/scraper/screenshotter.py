import hashlib
import logging
import re
from pathlib import Path

from playwright.async_api import async_playwright

from agentic_scraper.backend.config.messages import MSG_ERROR_SCREENSHOT_FAILED

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Sanitize string for safe filename."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", text)[:80]


async def capture_screenshot(url: str, output_dir: str, name_hint: str | None = None) -> str | None:
    """
    Captures a full-page screenshot of the given URL and saves it in the output directory.

    Args:
        url (str): The URL to capture.
        output_dir (str): The directory to save the screenshot in.
        name_hint (Optional[str]): Optional name hint for the output file.

    Returns:
        str: Path to the saved screenshot, or None if failed.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    safe_name = slugify(name_hint or url)
    hash_suffix = hashlib.blake2b(url.encode(), digest_size=6).hexdigest()
    file_path = Path(output_dir) / f"{safe_name}_{hash_suffix}.png"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1280, "height": 800})
            await page.goto(url, wait_until="networkidle", timeout=15000)
            await page.screenshot(path=file_path, full_page=True)
            await browser.close()
            return str(file_path)
    except Exception:
        logger.exception(MSG_ERROR_SCREENSHOT_FAILED, url)
        return None
