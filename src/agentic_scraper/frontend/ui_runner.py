"""
UI runner for triggering and monitoring scraping via the backend API.

This module validates user input, constructs API requests, and displays real-time
feedback using Streamlit. It includes:

- Token-authenticated requests to the backend scraping endpoint
- Integration with session state for caching and deduplication
- Live error reporting, input validation, and result summarization
"""

import asyncio
import logging
import time

import httpx
import streamlit as st

from agentic_scraper import __api_version__ as api_version
from agentic_scraper.config.constants import SCRAPER_CONFIG_FIELDS
from agentic_scraper.config.messages import (
    MSG_DEBUG_SCRAPE_CONFIG_MERGED,
    MSG_ERROR_EXTRACTION_FAILED,
    MSG_INFO_NO_VALID_URLS,
    MSG_INFO_USING_CACHE,
)
from agentic_scraper.config.models import ScrapedItem
from agentic_scraper.core.settings import get_settings
from agentic_scraper.frontend.models import PipelineConfig
from agentic_scraper.frontend.ui_runner_helpers import (
    attach_openai_config,
    parse_scraper_response,
    render_invalid_url_section,
    render_valid_url_feedback,
    summarize_results,
    validate_and_deduplicate_urls,
)

logger = logging.getLogger(__name__)
settings = get_settings()


async def start_scraping(urls: list[str], config: PipelineConfig) -> tuple[list[ScrapedItem], int]:
    """
    Make an authenticated API call to start scraping.

    Handles backend URL construction, OpenAI config attachment,
    and full response parsing. Displays errors directly in the UI.

    Args:
        urls (list[str]): Validated list of URLs to scrape.
        config (PipelineConfig): Scraping and OpenAI config parameters.

    Returns:
        tuple[list[ScrapedItem], int]: List of extracted items and count of skipped URLs.

    Raises:
        None. All errors are handled and displayed via Streamlit.
    """
    if "jwt_token" not in st.session_state:
        st.error("User is not authenticated!")
        return [], 0

    headers = {"Authorization": f"Bearer {st.session_state['jwt_token']}"}
    config_values = config.model_dump(include=set(SCRAPER_CONFIG_FIELDS))
    logger.debug(MSG_DEBUG_SCRAPE_CONFIG_MERGED.format(config=config_values))

    body = {
        "urls": urls,
        "agent_mode": config.agent_mode,
        "fetch_concurrency": config.fetch_concurrency,
        "screenshot_enabled": config.screenshot_enabled,
        "verbose": config.verbose,
        "retry_attempts": config.retry_attempts,
    }

    if config.agent_mode != "rule_based" and not attach_openai_config(config, body):
        return [], 0

    try:
        with st.spinner("🔍 Scraping in progress..."):
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.backend_domain}/api/{api_version}/scrape/start",
                    json=body,
                    headers=headers,
                    timeout=60,
                )

        response.raise_for_status()
        return parse_scraper_response(response.json())

    except httpx.RequestError as e:
        st.error(f"Request error: {e}")
    except httpx.HTTPStatusError as e:
        st.error(f"HTTP error {e.response.status_code}: {e.response.text}")
    except (ValueError, TypeError) as e:
        st.error(f"Unexpected response error: {e}")

    return [], 0


def run_scraper_pipeline(raw_input: str, config: PipelineConfig) -> tuple[list[ScrapedItem], int]:
    """
    Validate user input, initiate the scraping API request, and display results.

    Handles deduplication, caching (to avoid duplicate API calls), and exception handling.

    Args:
        raw_input (str): Raw multiline string of URLs from the input box.
        config (PipelineConfig): Scraper configuration selected via sidebar.

    Returns:
        tuple[list[ScrapedItem], int]: Extracted items and number of skipped or failed URLs.

    Raises:
        None. Errors are caught and shown using Streamlit warnings or error messages.
    """
    urls, invalid_lines = validate_and_deduplicate_urls(raw_input)
    render_invalid_url_section(invalid_lines)

    if not urls:
        st.warning(MSG_INFO_NO_VALID_URLS)
        return [], 0

    render_valid_url_feedback(urls)

    start = time.perf_counter()
    key = tuple(sorted(urls))

    try:
        if st.session_state.get("last_input_key") == key:
            st.info(MSG_INFO_USING_CACHE)
            return st.session_state["extracted_items"], 0

        items, skipped = asyncio.run(start_scraping(urls, config))

        st.session_state["extracted_items"] = items
        st.session_state["last_input_key"] = key

    except (RuntimeError, ValueError) as e:
        st.error(MSG_ERROR_EXTRACTION_FAILED.format(error=e))
        return [], 0

    summarize_results(items, skipped, start)
    return items, skipped
