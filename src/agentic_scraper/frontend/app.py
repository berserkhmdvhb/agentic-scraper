import asyncio
import sys

import pandas as pd
import streamlit as st

# --- WINDOWS ASYNCIO FIX ---
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from st_aggrid import AgGrid, GridOptionsBuilder

from agentic_scraper.backend.config.messages import (
    MSG_INFO_EXTRACTION_COMPLETE,
    MSG_INFO_FETCHING_URLS,
)
from agentic_scraper.backend.core.logger_setup import get_logger, setup_logging
from agentic_scraper.backend.core.settings import get_environment
from agentic_scraper.backend.scraper.agent import extract_structured_data
from agentic_scraper.backend.scraper.fetcher import fetch_all
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.backend.scraper.parser import extract_main_text
from agentic_scraper.backend.utils.validators import clean_input_urls, deduplicate_urls

# --- LOGGING SETUP ---
setup_logging(reset=True)
logger = get_logger()

# --- STREAMLIT CONFIG ---
st.set_page_config(page_title="Agentic Scraper", layout="wide")
st.sidebar.markdown(f"**Environment:** `{get_environment()}`")

st.title("🕵️ Agentic Scraper")
st.markdown("Extract structured data from any list of URLs using LLM-powered parsing.")

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


# --- CACHED PROCESSING PIPELINE ---
@st.cache_data(show_spinner=False)
def run_pipeline(urls: list[str]) -> list[ScrapedItem]:
    async def pipeline() -> list[ScrapedItem]:
        logger.info(MSG_INFO_FETCHING_URLS.format(len(urls)))
        fetch_results = await fetch_all(urls)
        tasks = []
        for url, html in fetch_results.items():
            if html.startswith("__FETCH_ERROR__"):
                continue
            text = extract_main_text(html)
            tasks.append(extract_structured_data(text, url=url))

        num_failures = sum(
            1 for html in fetch_results.values() if html.startswith("__FETCH_ERROR__")
        )
        logger.info("Skipped %d URLs due to fetch errors", num_failures)

        results = await asyncio.gather(*tasks)
        logger.info(MSG_INFO_EXTRACTION_COMPLETE.format(len(results)))
        return results

    return asyncio.run(pipeline())


# --- EXECUTION TRIGGER ---
if st.button("🚀 Run Extraction") and raw_input.strip():
    with st.spinner("Validating URLs..."):
        all_lines = [line.strip() for line in raw_input.strip().splitlines() if line.strip()]
        valid_urls = clean_input_urls(raw_input)
        invalid_lines = [line for line in all_lines if line not in valid_urls]

        urls = deduplicate_urls(valid_urls)

    if invalid_lines:
        st.info(f"ℹ️ {len(invalid_lines)} line(s) were skipped due to invalid URL formatting.")  # noqa: RUF001

    if not urls:
        st.warning("No valid URLs found.")
        st.session_state.valid_urls = []
        st.session_state.extracted_items = []
    else:
        st.session_state.valid_urls = urls
        st.success(f"✅ {len(urls)} valid URLs detected.")
        st.markdown("---")
        with st.spinner("⏳ Processing..."):
            try:
                items = run_pipeline(urls)
            except ValueError as e:
                st.error(f"❌ LLM extraction failed: {e}")
                items = []

        st.session_state.extracted_items = items

# --- RESULTS DISPLAY ---
if "extracted_items" in st.session_state and st.session_state.extracted_items:
    df_extracted_data = pd.DataFrame(
        [
            {**item.model_dump(exclude={"url"}), "url": str(item.url)}
            for item in st.session_state.extracted_items
        ]
    )

    if "screenshot_path" in df_extracted_data.columns:
        df_extracted_data = df_extracted_data[
            [col for col in df_extracted_data.columns if col != "screenshot_path"]
            + ["screenshot_path"]
        ]

    st.session_state.results_df = df_extracted_data

    st.success("✅ Extraction complete.")

    tab1, tab2 = st.tabs(["📊 Table Preview", "🖼️ Screenshot Preview"])

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
            "💾 Download JSON",
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
