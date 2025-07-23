import asyncio
import time
from dataclasses import dataclass
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


@dataclass
class PipelineConfig:
    fetch_concurrency: int
    llm_concurrency: int
    screenshot_enabled: bool
    log_tracebacks: bool
    openai_model: str
    agent_mode: str


def validate_and_deduplicate_urls(raw_input: str) -> tuple[list[str], list[str]]:
    all_lines = [line.strip() for line in raw_input.strip().splitlines() if line.strip()]
    valid_urls = clean_input_urls(raw_input)
    invalid_lines = [line for line in all_lines if line not in valid_urls]
    return deduplicate_urls(valid_urls), invalid_lines


async def run_scraper_pipeline(
    urls: list[str],
    config: PipelineConfig,
) -> ScrapeResultWithSkipCount:
    logger.info(MSG_INFO_FETCHING_URLS.format(len(urls)))

    settings = get_settings().model_copy(
        update={
            "fetch_concurrency": config.fetch_concurrency,
            "llm_concurrency": config.llm_concurrency,
            "screenshot_enabled": config.screenshot_enabled,
            "debug_mode": config.log_tracebacks,
            "openai_model": config.openai_model,
            "agent_mode": config.agent_mode,
        }
    )

    with st.status("🌐 **Fetching pages...**", expanded=True) as fetch_status:
        fetch_results = await fetch_all(
            urls=urls,
            concurrency=config.fetch_concurrency,
            settings=settings,
        )
        fetch_status.update(label="✅ **Fetched all pages**", state="complete")

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
    total = len(inputs)
    progress = st.progress(0, text="🧠 Starting LLM extraction...")
    status_line = st.empty()
    start_time = time.perf_counter()

    def on_item_processed(item: ScrapedItem) -> None:
        nonlocal processed
        processed += 1
        elapsed = time.perf_counter() - start_time
        est_total = (elapsed / processed) * total
        est_remaining = est_total - elapsed
        progress.progress(
            processed / total, text=f"🧠 {processed}/{total} — Est: {est_remaining:.1f}s left"
        )
        status_line.markdown(f"🔄 Processing: [{item.url}]({item.url})")

    def on_error(url: str, e: Exception) -> None:
        st.warning(f"⚠️ Failed to process {url}: {e}")
        logger.error(MSG_ERROR_PROCESSING_URL_FAILED)

    # Use auto-collapsing expander instead of persistent status box
    with st.expander("🧠 LLM Extraction Log", expanded=False):
        items = await run_worker_pool(
            inputs=inputs,
            settings=settings,
            concurrency=config.llm_concurrency,
            take_screenshot=config.screenshot_enabled,
            on_item_processed=on_item_processed,
            on_error=on_error,
            log_tracebacks=config.log_tracebacks,
        )
        st.success("✅ LLM extraction completed")

    logger.info(MSG_INFO_EXTRACTION_COMPLETE.format(len(items)))
    return items, skipped


def process_and_run(
    raw_input: str,
    config: PipelineConfig,
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

    st.session_state["is_running"] = True
    start = time.perf_counter()

    try:
        key = tuple(sorted(urls))
        if "last_input_key" in st.session_state and st.session_state.last_input_key == key:
            st.info("🔁 Using cached results for these URLs.")
            items = st.session_state.extracted_items
            skipped = 0
        else:
            items, skipped = asyncio.run(
                run_scraper_pipeline(
                    urls=urls,
                    config=config,
                )
            )
            st.session_state.extracted_items = items
            st.session_state.last_input_key = key

    except ValueError as e:
        st.error(f"❌ LLM extraction failed: {e}")
        st.write("🚫 Aborting due to an error.")
        st.session_state.extracted_items = []
        st.session_state.last_input_key = None
        return [], 0

    else:
        elapsed = round(time.perf_counter() - start, 2)

        # Display summary metrics (above the fold)
        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Extracted", f"{len(items)} URLs")
        col2.metric("⚠️ Skipped", f"{skipped} URLs")
        col3.metric("⏱️ Time", f"{elapsed:.2f}s")

        if items:
            st.write(f"✅ **Extracted structured data from `{len(items)}` URLs.**")
            if skipped > 0:
                st.warning(f"⚠️ Skipped {skipped} URL(s) due to fetch or parse errors.")

            with st.expander("🔍 View individual results"):
                for item in items:
                    title = item.title or "Untitled"
                    st.markdown(f"- 🔗 [{item.url}]({item.url}) — ✅ **{title}**")
        else:
            st.write("⚠️ No structured data extracted.")

        st.toast("✅ Extraction done!", icon="🎉")

        return items, skipped


def maybe_run_pipeline(raw_input: str, controls: dict[str, Any]) -> tuple[list[ScrapedItem], int]:
    config = PipelineConfig(
        fetch_concurrency=controls["fetch_concurrency"],
        llm_concurrency=controls["llm_concurrency"],
        screenshot_enabled=controls["screenshot_enabled"],
        log_tracebacks=controls["log_tracebacks"],
        openai_model=controls["openai_model"],
        agent_mode=controls["agent_mode"],
    )
    return process_and_run(raw_input=raw_input, config=config)
