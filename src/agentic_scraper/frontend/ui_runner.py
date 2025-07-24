import asyncio
import time
from typing import Any

import streamlit as st

from agentic_scraper.backend.config.aliases import ScrapeResultWithSkipCount
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_EXTRACTION_FAILED,
    MSG_ERROR_PROCESSING_URL_FAILED,
    MSG_INFO_EXTRACTION_COMPLETE,
    MSG_INFO_FETCH_SKIPPED,
    MSG_INFO_FETCHING_URLS,
    MSG_INFO_NO_VALID_URLS,
    MSG_INFO_USING_CACHE,
    MSG_INFO_VALID_URLS_FOUND,
    MSG_WARN_PROCESSING_URL_FAILED,
    MSG_WARNING_EXTRACTION_NONE,
)
from agentic_scraper.backend.core.logger_setup import get_logger
from agentic_scraper.backend.core.settings import Settings, get_settings
from agentic_scraper.backend.scraper.fetcher import fetch_all
from agentic_scraper.backend.scraper.models import PipelineConfig, ScrapedItem
from agentic_scraper.backend.scraper.parser import extract_main_text
from agentic_scraper.backend.scraper.worker_pool import run_worker_pool
from agentic_scraper.backend.utils.validators import clean_input_urls, deduplicate_urls

logger = get_logger()

DOMAIN_EMOJIS = {
    "youtube.com": "🎮",
    "github.com": "💻",
    "amazon.com": "🍭",
    "medium.com": "✍️",
    "wikipedia.org": "📚",
    "google.com": "🔎",
}


def validate_and_deduplicate_urls(raw_input: str) -> tuple[list[str], list[str]]:
    all_lines = [line.strip() for line in raw_input.strip().splitlines() if line.strip()]
    valid_urls = clean_input_urls(raw_input)
    invalid_lines = [line for line in all_lines if line not in valid_urls]
    return deduplicate_urls(valid_urls), invalid_lines


def extract_domain_icon(url: str) -> str:
    url = str(url)
    for domain, emoji in DOMAIN_EMOJIS.items():
        if domain in url:
            return emoji
    return "🔗"


def display_error_summaries(fetch_errors: list[str], extraction_errors: list[str]) -> None:
    if fetch_errors:
        with st.expander("🌐 Fetch Errors (could not load page)"):
            for msg in fetch_errors:
                st.markdown(f"- ❌ `{msg}`")
    if extraction_errors:
        with st.expander("🧠 Extraction Errors (LLM or validation failed)"):
            for msg in extraction_errors:
                st.markdown(f"- ❌ `{msg}`")


async def fetch_and_prepare_inputs(
    urls: list[str], config: PipelineConfig, settings: Settings
) -> tuple[list[tuple[str, str]], list[str], int]:
    logger.info(MSG_INFO_FETCHING_URLS.format(n=len(urls)))

    with st.spinner("🌐 Fetching pages..."):
        fetch_results = await fetch_all(
            urls=urls,
            concurrency=config.fetch_concurrency,
            settings=settings,
        )

    skipped = 0
    inputs = []
    fetch_errors: list[str] = []

    for url, html in fetch_results.items():
        if html.startswith("__FETCH_ERROR__"):
            skipped += 1
            fetch_errors.append(f"{url} — {html.replace('__FETCH_ERROR__:', '').strip()}")
            continue
        text = extract_main_text(html)
        inputs.append((url, text))

    logger.info(MSG_INFO_FETCH_SKIPPED.format(n=skipped))
    return inputs, fetch_errors, skipped


async def display_progress(
    inputs: list[tuple[str, str]], config: PipelineConfig, settings: Settings
) -> tuple[list[ScrapedItem], list[str]]:
    processed = 0
    total = len(inputs)
    progress = st.progress(0)
    status_line = st.empty()
    start_time = time.perf_counter()

    log_box = st.expander("🧠 LLM Extraction Log", expanded=False)
    with log_box:
        st.caption("Processing progress will appear here.")

    extraction_errors: list[str] = []

    def on_item_processed(item: ScrapedItem) -> None:
        nonlocal processed
        processed += 1
        elapsed = time.perf_counter() - start_time
        est_total = (elapsed / processed) * total
        est_remaining = est_total - elapsed
        label = f"🧠 {processed}/{total} — Est: {est_remaining:.1f}s left"
        progress.progress(processed / total, text=label)
        status_line.markdown(f"🔄 Processing: [{item.url}]({item.url})")

    def on_error(url: str, e: Exception) -> None:
        extraction_errors.append(f"{url} — {e!s}")
        log_box.info(MSG_WARN_PROCESSING_URL_FAILED.format(url=url, error=e))
        if settings.is_verbose_mode:
            logger.exception(MSG_ERROR_PROCESSING_URL_FAILED)
        else:
            logger.error(MSG_ERROR_PROCESSING_URL_FAILED)

    items = await run_worker_pool(
        inputs=inputs,
        settings=settings,
        concurrency=config.llm_concurrency,
        take_screenshot=config.screenshot_enabled,
        on_item_processed=on_item_processed,
        on_error=on_error,
    )

    progress.empty()
    status_line.empty()

    with log_box:
        if items:
            st.info("✅ Extraction pipeline completed")
        else:
            st.warning("⚠️ No items processed. Pipeline ended with zero results.")

    return items, extraction_errors


async def run_scraper_pipeline(
    urls: list[str], config: PipelineConfig
) -> ScrapeResultWithSkipCount:
    settings = get_settings().model_copy(
        update={
            "fetch_concurrency": config.fetch_concurrency,
            "llm_concurrency": config.llm_concurrency,
            "screenshot_enabled": config.screenshot_enabled,
            "verbose": config.verbose,
            "openai_model": config.openai_model,
            "agent_mode": config.agent_mode,
            "retry_attempts": config.retry_attempts,
        }
    )

    sticky = st.empty()
    sticky.info("⏳ Currently processing...", icon="🔄")

    inputs, fetch_errors, skipped = await fetch_and_prepare_inputs(urls, config, settings)
    items, extraction_errors = await display_progress(inputs, config, settings)
    sticky.empty()
    display_error_summaries(fetch_errors, extraction_errors)

    if items:
        logger.info(MSG_INFO_EXTRACTION_COMPLETE.format(n=len(items)))
    else:
        logger.warning(MSG_WARNING_EXTRACTION_NONE)

    return items, skipped


def process_and_run(raw_input: str, config: PipelineConfig) -> tuple[list[ScrapedItem], int]:
    urls, invalid_lines = validate_and_deduplicate_urls(raw_input)

    if invalid_lines:
        with st.expander("⚠️ Skipped Invalid URLs"):
            for url in invalid_lines:
                st.markdown(f"- ❌ `{url}` — *invalid URL format*")

    if not urls:
        st.warning(MSG_INFO_NO_VALID_URLS)
        st.session_state.valid_urls = []
        st.session_state.extracted_items = []
        return [], 0

    st.session_state.valid_urls = urls
    st.info(MSG_INFO_VALID_URLS_FOUND.format(n=len(urls)))
    st.markdown("---")

    st.session_state["is_running"] = True
    start = time.perf_counter()

    try:
        key = tuple(sorted(urls))
        if "last_input_key" in st.session_state and st.session_state.last_input_key == key:
            st.info(MSG_INFO_USING_CACHE)
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
        st.error(MSG_ERROR_EXTRACTION_FAILED.format(error=e))
        st.info("🚫 Aborting due to an error.")
        st.session_state.extracted_items = []
        st.session_state.last_input_key = None
        return [], 0

    else:
        elapsed = round(time.perf_counter() - start, 2)

        if not items:
            st.warning("⚠️ No data could be extracted. All URLs failed or were skipped.")
        else:
            st.markdown("## 🎉 Extraction Complete")
            col1, col2, col3 = st.columns(3)
            col1.metric("✅ Extracted", f"{len(items)} URLs")
            col2.metric("⚠️ Skipped", f"{skipped} URLs")
            col3.metric("⏱️ Time", f"{elapsed:.2f}s")

            with st.expander("🔍 Extracted URLs (Quick View)"):
                for item in items:
                    icon = extract_domain_icon(str(item.url))
                    title = (item.title or str(item.url)).strip()
                    st.markdown(f"- {icon} [{title}]({item.url})")

        return items, skipped


def maybe_run_pipeline(raw_input: str, controls: dict[str, Any]) -> tuple[list[ScrapedItem], int]:
    config = PipelineConfig(
        fetch_concurrency=controls["fetch_concurrency"],
        llm_concurrency=controls["llm_concurrency"],
        screenshot_enabled=controls["screenshot_enabled"],
        verbose=controls["verbose"],
        openai_model=controls["openai_model"],
        agent_mode=controls["agent_mode"],
        retry_attempts=controls["retry_attempts"],
    )
    return process_and_run(raw_input=raw_input, config=config)
