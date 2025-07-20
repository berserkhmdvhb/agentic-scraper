import asyncio
import sqlite3
import sys
from io import BytesIO

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

from agentic_scraper.backend.config.messages import (
    MSG_INFO_EXTRACTION_COMPLETE,
    MSG_INFO_FETCH_SKIPPED,
    MSG_INFO_FETCHING_URLS,
)
from agentic_scraper.backend.config.types import ScrapeResultWithSkipCount
from agentic_scraper.backend.core.logger_setup import get_logger, setup_logging
from agentic_scraper.backend.core.settings import get_environment
from agentic_scraper.backend.scraper.fetcher import fetch_all
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.backend.scraper.parser import extract_main_text
from agentic_scraper.backend.scraper.worker_pool import run_worker_pool
from agentic_scraper.backend.utils.validators import clean_input_urls, deduplicate_urls

# --- WINDOWS ASYNCIO FIX ---
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- LOGGING SETUP ---
setup_logging(reset=True)
logger = get_logger()

# --- STREAMLIT CONFIG ---
st.set_page_config(page_title="Agentic Scraper", layout="wide")
st.sidebar.markdown(f"**Environment:** `{get_environment()}`")

st.title("🕵️ Agentic Scraper")
st.markdown("Extract structured data from any list of URLs using LLM-powered parsing.")

# --- SIDEBAR OPTIONS ---
screenshot_enabled = st.sidebar.checkbox("📸 Enable Screenshot", value=False)
st.session_state["screenshot_enabled"] = screenshot_enabled

st.sidebar.markdown("### ⚙️ Performance Settings")
num_workers = st.sidebar.slider("Concurrency (number of workers)", 1, 20, 10)

# --- INPUT METHOD ---
input_method = st.radio("Input method:", ["Paste URLs", "Upload .txt file"], horizontal=True)

raw_input = ""
if input_method == "Paste URLs":
    raw_input = st.text_area(
        "Enter one URL per line:",
        height=200,
        placeholder="https://example.com\nhttps://another.com",
    )
elif input_method == "Upload .txt file":
    uploaded_file = st.file_uploader("Upload a .txt file with URLs", type=["txt"])
    if uploaded_file:
        try:
            raw_input = uploaded_file.read().decode("utf-8")
        except UnicodeDecodeError:
            st.error("\u274c Unable to decode file. Please upload a UTF-8 encoded .txt file.")


# --- EXECUTION TRIGGER ---
if st.button("🚀 Run Extraction") and raw_input.strip():
    with st.spinner("Validating URLs..."):
        all_lines = [line.strip() for line in raw_input.strip().splitlines() if line.strip()]
        valid_urls = clean_input_urls(raw_input)
        invalid_lines = [line for line in all_lines if line not in valid_urls]

        urls = deduplicate_urls(valid_urls)

    if invalid_lines:
        st.info(f"⚠️ {len(invalid_lines)} line(s) were skipped due to invalid URL formatting.")

    if not urls:
        st.warning("⚠️ No valid URLs found.")
        st.session_state.valid_urls = []
        st.session_state.extracted_items = []
    else:
        st.session_state.valid_urls = urls
        st.success(f"✅ {len(urls)} valid URLs detected.")
        st.markdown("---")

        with st.status("🔄 **Running scraping pipeline...**", expanded=True) as status:
            st.write(f"📥 **Fetching `{len(urls)}` URLs...**")

            async def run_async_extraction() -> ScrapeResultWithSkipCount:
                logger.info(MSG_INFO_FETCHING_URLS.format(len(urls)))
                fetch_results = await fetch_all(urls)

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

                items = await run_worker_pool(
                    inputs=inputs,
                    num_workers=num_workers,
                    take_screenshot=screenshot_enabled,
                    on_item_processed=on_item_processed,
                    on_error=on_error,
                    log_tracebacks=False,
                )

                logger.info(MSG_INFO_EXTRACTION_COMPLETE.format(len(items)))
                return items, skipped

            try:
                items, skipped = asyncio.run(run_async_extraction())

                if items:
                    st.write(f"✅ **Extracted structured data from `{len(items)}` URLs.**")
                    if skipped > 0:
                        st.warning(f"⚠️ Skipped `{skipped}` URL(s) due to fetch or parse errors.")
                else:
                    st.write("⚠️ No structured data extracted.")

                status.update(label="✅ **Scraping completed!**", state="complete")

                if items:
                    with st.expander("🔍 View individual results"):
                        for item in items:
                            st.markdown(
                                f"- 🔗 [{item.url}]({item.url}) — ✅ **{item.title or 'Untitled'}**"
                            )

            except ValueError as e:
                st.error(f"❌ LLM extraction failed: {e}")
                st.write("🚫 Aborting due to an error.")
                status.update(label="❌ **Error during scraping**", state="error")
                items = []

            st.session_state.extracted_items = items


# --- RESULTS DISPLAY ---
if "extracted_items" in st.session_state and st.session_state.extracted_items:
    st.markdown("### 📊 **Display Results**")
    df_extracted_data = pd.DataFrame(
        [
            {**item.model_dump(exclude={"url"}), "url": str(item.url)}
            for item in st.session_state.extracted_items
        ]
    )

    if not screenshot_enabled and "screenshot_path" in df_extracted_data.columns:
        df_extracted_data = df_extracted_data.drop(columns=["screenshot_path"])

    if "screenshot_path" in df_extracted_data.columns:
        df_extracted_data = df_extracted_data[
            [col for col in df_extracted_data.columns if col != "screenshot_path"]
            + ["screenshot_path"]
        ]

    st.session_state.results_df = df_extracted_data

    if screenshot_enabled:
        tab1, tab2 = st.tabs(["📋 Extracted Table", "🗼 Screenshot Details"])
    else:
        (tab1,) = st.tabs(["📋 Table Preview"])

    with tab1:
        display_df = df_extracted_data.drop(columns=["screenshot_path"], errors="ignore")
        gb = GridOptionsBuilder.from_dataframe(display_df)
        gb.configure_column("screenshot_path", hide=True)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_default_column(filter=True, sortable=True, resizable=True)
        grid_options = gb.build()

        AgGrid(
            display_df,
            gridOptions=grid_options,
            enable_enterprise_modules=False,
            fit_columns_on_grid_load=True,
            theme="streamlit",
        )

        st.download_button(
            "📅 Download JSON",
            df_extracted_data.to_json(orient="records", indent=2),
            "results.json",
            mime="application/json",
        )

        st.download_button(
            "📄 Download CSV",
            df_extracted_data.to_csv(index=False),
            "results.csv",
            mime="text/csv",
        )

        def dataframe_to_sqlite_bytes(
            df: pd.DataFrame, table_name: str = "scraped_data"
        ) -> BytesIO:
            buffer = BytesIO()
            with sqlite3.connect(":memory:") as conn:
                df.to_sql(table_name, conn, index=False, if_exists="replace")
                for line in conn.iterdump():
                    buffer.write(f"{line}\n".encode())
            buffer.seek(0)
            return buffer

        sqlite_bytes = dataframe_to_sqlite_bytes(df_extracted_data)
        st.download_button(
            "🗃️ Download SQLite",
            data=sqlite_bytes,
            file_name="results.sqlite",
            mime="application/x-sqlite3",
        )

    if screenshot_enabled:
        with tab2:
            for item in st.session_state.extracted_items:
                if item.screenshot_path:
                    with st.expander(f"🔗 [{item.url}]({item.url})"):
                        if item.title:
                            st.markdown(f"### {item.title}")
                        st.markdown(f"**URL:** [{item.url}]({item.url})")
                        st.markdown(f"**Description:** {item.description or '_No description_'}")
                        st.image(item.screenshot_path, width=500)

elif "extracted_items" in st.session_state and not st.session_state.extracted_items:
    st.error("No successful extractions.")

# --- RESET BUTTON ---
if st.sidebar.button("🔄 Reset"):
    st.session_state.clear()
    st.rerun()
