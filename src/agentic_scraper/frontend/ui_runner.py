import asyncio
import time

import httpx
import streamlit as st

from agentic_scraper import __api_version__ as api_version
from agentic_scraper.backend.config.constants import SCRAPER_CONFIG_FIELDS
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_EXTRACTION_FAILED,
    MSG_INFO_NO_VALID_URLS,
    MSG_INFO_USING_CACHE,
)
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.frontend.models import PipelineConfig
from agentic_scraper.frontend.ui_runner_helpers import (
    render_invalid_url_section,
    render_valid_url_feedback,
    summarize_results,
    validate_and_deduplicate_urls,
)

settings = get_settings()


async def start_scraping(urls: list[str], config: PipelineConfig) -> tuple[list[ScrapedItem], int]:
    """Make API call to start scraping with the JWT token and optional OpenAI credentials."""
    if "jwt_token" not in st.session_state:
        st.error("User is not authenticated!")
        return [], 0

    headers = {"Authorization": f"Bearer {st.session_state['jwt_token']}"}
    config_values = config.model_dump(include=set(SCRAPER_CONFIG_FIELDS))

    body = {
        "urls": urls,
        "agent_mode": config.agent_mode,
        "fetch_concurrency": config.fetch_concurrency,
        "screenshot_enabled": config.screenshot_enabled,
        "verbose": config.verbose,
        "retry_attempts": config.retry_attempts,
    }

    if config.agent_mode != "rule_based":
        openai_credentials = st.session_state.get("openai_credentials")
        if not openai_credentials:
            st.error("OpenAI credentials are missing!")
            return [], 0

        body.update(
            {
                "openai_credentials": openai_credentials.model_dump(),
                "openai_model": config.openai_model,
                "llm_concurrency": config.llm_concurrency,
                "llm_schema_retries": config.llm_schema_retries,
            }
        )

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

        data = response.json()
        raw_items = data.get("results", [])
        skipped = data.get("stats", {}).get("skipped", 0)

        items = []
        for idx, item in enumerate(raw_items):
            if isinstance(item, dict):
                try:
                    items.append(ScrapedItem(**item))
                except Exception as e:
                    st.warning(f"⚠️ Skipped malformed result #{idx + 1}: {e}")
            elif isinstance(item, ScrapedItem):
                items.append(item)
            else:
                st.warning(f"⚠️ Skipped unexpected type result #{idx + 1}: {type(item)}")

        return items, skipped

    except httpx.RequestError as e:
        st.error(f"Request error: {e}")
    except httpx.HTTPStatusError as e:
        st.error(f"HTTP error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")

    return [], 0


def run_scraper_pipeline(raw_input: str, config: PipelineConfig) -> tuple[list[ScrapedItem], int]:
    """Main entry to validate input, run scraper via API, and display results."""
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

    except Exception as e:
        st.error(MSG_ERROR_EXTRACTION_FAILED.format(error=e))
        return [], 0

    summarize_results(items, skipped, start)
    return items, skipped
