import asyncio
import logging

import pandas as pd
import streamlit as st

from agentic_scraper.backend.core.logger_setup import setup_logging
from agentic_scraper.backend.core.settings import get_environment
from agentic_scraper.backend.scraper.agent import extract_structured_data
from agentic_scraper.backend.scraper.fetcher import fetch_all
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.backend.scraper.parser import extract_main_text
from agentic_scraper.backend.utils.validators import clean_input_urls, deduplicate_urls

# --- LOGGING SETUP ---
setup_logging(reset=True)
logger = logging.getLogger(__name__)

# --- STREAMLIT CONFIG ---
st.set_page_config(page_title="Agentic Scraper", layout="wide")
st.sidebar.markdown(f"**Environment:** `{get_environment()}`")

st.title("🕵️ Agentic Scraper")
st.markdown("Extract structured data from any list of URLs using LLM-powered parsing.")

# --- INPUT METHOD ---
input_method = st.radio("Input method:", ["Paste URLs", "Upload .txt file"], horizontal=True)

if input_method == "Paste URLs":
    raw_input = st.text_area(
        "Enter one URL per line:",
        height=200,
        placeholder="https://example.com\nhttps://another.com",
    )
elif input_method == "Upload .txt file":
    uploaded_file = st.file_uploader("Upload a .txt file with URLs")
    raw_input = uploaded_file.read().decode("utf-8") if uploaded_file else ""


# --- CACHED PROCESSING PIPELINE ---
@st.cache_data(show_spinner=False)
def run_pipeline(urls: list[str]) -> list[ScrapedItem]:
    async def pipeline() -> list[ScrapedItem]:
        logger.info("Fetching and processing %d URLs", len(urls))
        fetch_results = await fetch_all(urls)
        tasks = []
        for url, html in fetch_results.items():
            if html.startswith("__FETCH_ERROR__"):
                continue
            text = extract_main_text(html)
            tasks.append(extract_structured_data(text, url=url))
        results = await asyncio.gather(*tasks)
        logger.info("Completed extraction for %d URLs", len(results))
        return results

    return asyncio.run(pipeline())


# --- EXECUTION TRIGGER ---
if st.button("🚀 Run Extraction") and raw_input.strip():
    with st.spinner("Validating URLs..."):
        urls = deduplicate_urls(clean_input_urls(raw_input))

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

    # Reorder columns for UX: move screenshot_path to the end
    if "screenshot_path" in df_extracted_data.columns:
        df_extracted_data = df_extracted_data[
            [col for col in df_extracted_data.columns if col != "screenshot_path"]
            + ["screenshot_path"]
        ]

    st.session_state.results_df = df_extracted_data

    st.success("✅ Extraction complete.")
    st.dataframe(df_extracted_data, use_container_width=True)

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

    # --- Screenshot Preview ---
    if "screenshot_path" in df_extracted_data.columns:
        st.markdown("### 🖼️ Screenshots (if available)")
        for item in st.session_state.extracted_items:
            if item.screenshot_path:
                st.image(
                    item.screenshot_path, caption=item.title or "Screenshot", use_column_width=True
                )

elif "extracted_items" in st.session_state and not st.session_state.extracted_items:
    st.error("No successful extractions.")


# --- RESET BUTTON ---
if st.sidebar.button("🔄 Reset"):
    st.session_state.clear()
    st.rerun()
