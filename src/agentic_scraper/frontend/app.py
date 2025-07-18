import asyncio
import logging

import pandas as pd
import streamlit as st

from agentic_scraper.backend.scraper.agent import extract_structured_data
from agentic_scraper.backend.scraper.fetcher import fetch_all
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.backend.scraper.parser import extract_main_text
from agentic_scraper.backend.validators import clean_input_urls, deduplicate_urls

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# --- STREAMLIT CONFIG ---
st.set_page_config(page_title="Agentic Scraper", layout="wide")
st.title("🕵️ Agentic Scraper")
st.markdown("Extract structured data from any list of URLs using LLM-powered parsing.")

# --- INPUT SECTION ---
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


# --- PROCESSING PIPELINE ---
@st.cache_data(show_spinner=False)
def run_pipeline(urls: list[str]) -> list[ScrapedItem]:
    def sync_wrapper() -> list[ScrapedItem]:
        async def run():
            fetch_results = await fetch_all(urls)
            tasks = []

            for url, html in fetch_results.items():
                if html.startswith("__FETCH_ERROR__"):
                    continue
                text = extract_main_text(html)
                tasks.append(extract_structured_data(text, url=url))

            return await asyncio.gather(*tasks)

        return asyncio.run(run())

    return asyncio.run(asyncio.to_thread(sync_wrapper))


# --- EXECUTION ---
if st.button("🚀 Run Extraction") and raw_input.strip():
    with st.spinner("Validating URLs..."):
        urls = deduplicate_urls(clean_input_urls(raw_input))

    if not urls:
        st.warning("No valid URLs found.")
    else:
        st.success(f"✅ {len(urls)} valid URLs detected.")
        st.markdown("---")
        st.markdown("### ⏳ Processing...")

        try:
            items = run_pipeline(urls)
        except ValueError as e:
            st.error(f"❌ LLM extraction failed: {e}")
            items = []

        # --- DISPLAY RESULTS ---
        if not items:
            st.error("No successful extractions.")
        else:
            df = pd.DataFrame([item.model_dump() for item in items])
            st.dataframe(df, use_container_width=True)

            st.download_button(
                "💾 Download JSON",
                df.to_json(orient="records", indent=2),
                "results.json",
                mime="application/json",
            )
            st.download_button(
                "📄 Download CSV", df.to_csv(index=False), "results.csv", mime="text/csv"
            )
