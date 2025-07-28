import time

import httpx
import streamlit as st
from fastapi import status

from agentic_scraper.backend.config.messages import MSG_INFO_NO_VALID_URLS
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.frontend.models import PipelineConfig
from agentic_scraper.frontend.ui_runner_helpers import (
    display_error_summaries,
    display_progress,
    fetch_and_prepare_inputs,
)

settings = get_settings()


async def start_scraping(urls: list[str], config: PipelineConfig) -> tuple[list[ScrapedItem], int]:
    """Make API call to start scraping with the JWT token and OpenAI credentials."""

    # Initialize result variables
    result = [], 0

    # Check for JWT token
    if "jwt_token" not in st.session_state:
        st.error("User is not authenticated!")
        return result

    # Fetch OpenAI credentials from session state
    openai_credentials = st.session_state.get("openai_credentials")
    if not openai_credentials:
        st.error("OpenAI credentials are missing!")
        return result

    headers = {
        "Authorization": f"Bearer {st.session_state['jwt_token']}",
    }

    # Prepare the request body with URLs, OpenAI credentials, and other configuration options
    body = {
        "urls": urls,
        "openai_credentials": openai_credentials,
        "fetch_concurrency": config.fetch_concurrency,
        "llm_concurrency": config.llm_concurrency,
        "openai_model": config.openai_model,
        "agent_mode": config.agent_mode,
        "retry_attempts": config.retry_attempts,
        "llm_schema_retries": config.llm_schema_retries,
        "screenshot_enabled": config.screenshot_enabled,
        "verbose": config.verbose,
    }

    try:
        # Make the API request to start scraping
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://your-backend-url/api/v1/scrape/start",  # Your backend scrape endpoint
                json=body,
                headers=headers,
            )

            # Handle response
            if response.status_code == status.HTTP_202_ACCEPTED:
                st.success("Scraping started!")
                result = response.json(), 0  # Return the response data if successful
            else:
                st.error(f"Failed to start scraping: {response.text}")
    except httpx.HTTPStatusError as e:
        st.error(f"HTTP status error occurred: {e!s}")
    except httpx.RequestError as e:
        st.error(f"Request error occurred: {e!s}")
    except RuntimeError as e:
        st.error(f"A runtime error occurred: {e!s}")

    return result


async def run_scraper_pipeline(
    urls: list[str], config: PipelineConfig
) -> tuple[list[ScrapedItem], int]:
    """Run the entire scraper pipeline."""
    if not urls:
        st.warning(MSG_INFO_NO_VALID_URLS)
        return [], 0

    # Prepare inputs
    inputs, fetch_errors, skipped = await fetch_and_prepare_inputs(
        urls=urls, fetch_concurrency=config.fetch_concurrency, settings=settings
    )

    # Track progress and display results
    items, extraction_errors = await display_progress(
        inputs=inputs, total=len(urls), processed=0, start_time=time.perf_counter()
    )

    # Display error summaries (fetch and extraction errors)
    display_error_summaries(fetch_errors, extraction_errors)

    # Trigger the API call to start scraping
    items, skipped = await start_scraping(urls, config)

    # You may want to further process the API response here if needed
    # For example, display the returned results (scraped items) in a user-friendly way
    if items:
        st.markdown("### 🎉 Scraping Complete!")
        for item in items:
            st.write(item)  # You can customize how to display the items

    return items, skipped
