import asyncio
import time
from typing import Any

import streamlit as st

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_PROCESSING_URL_FAILED,
    MSG_INFO_EXTRACTION_COMPLETE,
    MSG_INFO_FETCH_SKIPPED,
    MSG_INFO_FETCHING_URLS,
)
from agentic_scraper.backend.config.types import ScrapeResultWithSkipCount
from agentic_scraper.backend.core.logger_setup import get_logger
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.backend.scraper.fetcher import fetch_all
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.backend.scraper.parser import extract_main_text
from agentic_scraper.backend.scraper.worker_pool import run_worker_pool
from agentic_scraper.backend.utils.validators import clean_input_urls, deduplicate_urls

logger = get_logger()


def validate_and_deduplicate_urls(raw_input: str) -> tuple[list[str], list[str]]:
    """
    Validate and clean user input, returning (valid_urls, invalid_lines).
    """
    all_lines = [line.strip() for line in raw_input.strip().splitlines() if line.strip()]
    valid_urls = clean_input_urls(raw_input)
    invalid_lines = [line for line in all_lines if line not in valid_urls]
    return deduplicate_urls(valid_urls), invalid_lines


async def run_scraper_pipeline(  # noqa: PLR0913
    urls: list[str],
    fetch_concurrency: int,
    llm_concurrency: int,
    *,
    screenshot_enabled: bool,
    log_tracebacks: bool,
    agent_mode: str,
) -> ScrapeResultWithSkipCount:
    logger.info(MSG_INFO_FETCHING_URLS.format(len(urls)))

    settings = get_settings().model_copy(
        update={
            "fetch_concurrency": fetch_concurrency,
            "llm_concurrency": llm_concurrency,
            "screenshot_enabled": screenshot_enabled,
            "debug_mode": log_tracebacks,
            "agent_mode": agent_mode,
        }
    )

    fetch_results = await fetch_all(
        urls=urls,
        concurrency=fetch_concurrency,
        settings=settings,
    )

    skipped = 0
    inputs = []
    for url, html in fetch_results.items():
        if html.startswith("__FETCH_ERROR__"):
            skipped += 1
            continue
        text = extract_main_text(html)
        inputs.append((url, text))

    logger.info(MSG_INFO_FETCH_SKIPPED, skipped)
    processed = 0
    status_area = st.empty()

    def on_item_processed(item: ScrapedItem) -> None:
        nonlocal processed
        processed += 1
        status_area.write(f"✅ {processed}/{len(inputs)}: {item.url}")

    def on_error(url: str, e: Exception) -> None:
        st.warning(f"⚠️ Failed to process {url}: {e}")
        logger.error(MSG_ERROR_PROCESSING_URL_FAILED)

    items = await run_worker_pool(
        inputs=inputs,
        settings=settings,
        concurrency=llm_concurrency,
        take_screenshot=screenshot_enabled,
        on_item_processed=on_item_processed,
        on_error=on_error,
    )

    logger.info(MSG_INFO_EXTRACTION_COMPLETE.format(len(items)))
    return items, skipped


def process_and_run(  # noqa: PLR0913
    raw_input: str,
    fetch_concurrency: int,
    llm_concurrency: int,
    agent_mode: str,
    *,
    screenshot_enabled: bool,
    log_tracebacks: bool,
) -> tuple[list[ScrapedItem], int]:
    urls, invalid_lines = validate_and_deduplicate_urls(raw_input)

    if invalid_lines:
        st.info(f"⚠️ {len(invalid_lines)} line(s) were skipped due to invalid URL formatting.")

    if not urls:
        st.warning("⚠️ No valid URLs found.")
        st.session_state.valid_urls = []
        st.session_state.extracted_items = []
        return [], 0

    st.session_state.valid_urls = urls
    st.success(f"✅ {len(urls)} valid URLs detected.")
    st.markdown("---")

    with st.status("🔄 **Running scraping pipeline...**", expanded=True) as status:
        start = time.perf_counter()
        st.write(f"📥 **Fetching `{len(urls)}` URLs...**")

        key = tuple(sorted(urls))
        try:
            if "last_input_key" in st.session_state and st.session_state.last_input_key == key:
                st.info("🔁 Using cached results for these URLs.")
                items = st.session_state.extracted_items
                skipped = 0
            else:
                items, skipped = asyncio.run(
                    run_scraper_pipeline(
                        urls=urls,
                        fetch_concurrency=fetch_concurrency,
                        llm_concurrency=llm_concurrency,
                        screenshot_enabled=screenshot_enabled,
                        log_tracebacks=log_tracebacks,
                        agent_mode=agent_mode,
                    )
                )
                st.session_state.extracted_items = items
                st.session_state.last_input_key = key

        except ValueError as e:
            st.error(f"❌ LLM extraction failed: {e}")
            st.write("🚫 Aborting due to an error.")
            status.update(label="❌ **Error during scraping**", state="error")
            st.session_state.extracted_items = []
            st.session_state.last_input_key = None
            return [], 0

        else:
            if items:
                st.write(f"✅ **Extracted structured data from `{len(items)}` URLs.**")
                if skipped > 0:
                    st.warning(f"⚠️ Skipped {skipped} URL(s) due to fetch or parse errors.")
            else:
                st.write("⚠️ No structured data extracted.")

            end = time.perf_counter()
            elapsed = round(end - start, 2)
            st.markdown(
                f"<div style='font-size: 1.1rem;'>"
                f"<b>⏱️ Processing Time:</b> {elapsed:.2f} seconds</div>",
                unsafe_allow_html=True,
            )
            status.update(label="✅ **Scraping completed!**", state="complete")

            if items:
                with st.expander("🔍 View individual results"):
                    for item in items:
                        title = item.title or "Untitled"
                        st.markdown(f"- 🔗 [{item.url}]({item.url}) — ✅ **{title}**")

            return items, skipped


def maybe_run_pipeline(raw_input: str, controls: dict[str, Any]) -> tuple[list[ScrapedItem], int]:
    return process_and_run(
        raw_input=raw_input,
        fetch_concurrency=controls["fetch_concurrency"],
        llm_concurrency=controls["llm_concurrency"],
        screenshot_enabled=controls["screenshot_enabled"],
        log_tracebacks=controls["log_tracebacks"],
        agent_mode=controls["agent_mode"],
    )
