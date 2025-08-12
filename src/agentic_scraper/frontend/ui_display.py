"""
Display and export scraped results in the Streamlit frontend.

Robustness improvements:
- Avoid AgGrid config on missing columns
- Graceful handling when no rows exist
- Stable column ordering (URL first, screenshot last)
- Safer export fallbacks
"""

from __future__ import annotations

import json
import sqlite3
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st
from pydantic import HttpUrl
from st_aggrid import AgGrid, GridOptionsBuilder

if TYPE_CHECKING:
    from agentic_scraper.backend.scraper.models import ScrapedItem


def dataframe_to_sqlite_bytes(df: pd.DataFrame, table_name: str = "scraped_data") -> BytesIO:
    """Convert a DataFrame into a SQLite memory DB and return it as a BytesIO buffer."""
    buffer = BytesIO()
    df_serialized = df.copy()

    def safe_serialize(x: object) -> str | object:
        if isinstance(x, (list, dict)):
            return json.dumps(x)
        if isinstance(x, (HttpUrl, Path)):
            return str(x)
        return x

    if not df_serialized.empty:
        for col in df_serialized.columns:
            df_serialized[col] = df_serialized[col].apply(safe_serialize)

    with sqlite3.connect(":memory:") as conn:
        df_serialized.to_sql(table_name, conn, index=False, if_exists="replace")
        for line in conn.iterdump():
            buffer.write(f"{line}\n".encode())

    buffer.seek(0)
    return buffer


def _stable_column_order(df: pd.DataFrame) -> pd.DataFrame:
    """Place 'url' first and 'screenshot_path' last when present."""
    cols = list(df.columns)
    if not cols:
        return df

    # Move URL first
    if "url" in cols:
        cols.remove("url")
        cols.insert(0, "url")

    # Move screenshot last
    if "screenshot_path" in cols:
        cols.remove("screenshot_path")
        cols.append("screenshot_path")

    return df[cols]


def prepare_dataframe(items: list[ScrapedItem], *, screenshot_enabled: bool) -> pd.DataFrame:
    """Convert scraped items into a cleaned and ordered DataFrame."""
    if not items:
        return pd.DataFrame()

    df_extracted = pd.DataFrame(
        [{**item.model_dump(exclude={"url"}), "url": str(item.url)} for item in items]
    )

    if not screenshot_enabled and "screenshot_path" in df_extracted.columns:
        df_extracted = df_extracted.drop(columns=["screenshot_path"])  # hide entirely

    return _stable_column_order(df_extracted)


def display_data_table(df: pd.DataFrame) -> None:
    """Render the extracted data using an interactive AgGrid table."""
    if df.empty:
        st.info("No rows to display yet.")
        return

    gb = GridOptionsBuilder.from_dataframe(df)
    if "screenshot_path" in df.columns:
        gb.configure_column("screenshot_path", hide=True)  # keep column but hidden
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_default_column(filter=True, sortable=True, resizable=True)
    grid_options = gb.build()

    AgGrid(
        df,
        gridOptions=grid_options,
        enable_enterprise_modules=False,
        fit_columns_on_grid_load=True,
        theme="streamlit",
    )


def display_results(
    items: list[ScrapedItem],
    *,
    screenshot_enabled: bool,
) -> None:
    """Display extracted data with optional screenshots and download buttons."""
    st.markdown("### 📊 **Display Results**")

    df_extracted = prepare_dataframe(items, screenshot_enabled=screenshot_enabled)
    st.session_state.results_df = df_extracted

    if df_extracted.empty:
        st.info("Nothing to show yet. Try running a scrape or adjust your filters.")
        return

    # Create tabs for viewing results
    if screenshot_enabled:
        tab1, tab2 = st.tabs(["📋 Extracted Table", "🖼️ Screenshot Details"])
    else:
        (tab1,) = st.tabs(["📋 Table Preview"])

    with tab1:
        display_data_table(df_extracted)

        # Export buttons
        st.download_button(
            "📅 Download JSON",
            df_extracted.to_json(orient="records", indent=2),
            "results.json",
            mime="application/json",
        )

        st.download_button(
            "📄 Download CSV",
            df_extracted.to_csv(index=False),
            "results.csv",
            mime="text/csv",
        )

        try:
            sqlite_bytes = dataframe_to_sqlite_bytes(df_extracted)
        except (sqlite3.Error, ValueError, TypeError) as e:
            st.error(f"❌ Failed to generate SQLite export: {e}")
            sqlite_bytes = BytesIO()
        st.download_button(
            "🗃️ Download SQLite",
            data=sqlite_bytes,
            file_name="results.sqlite",
            mime="application/x-sqlite3",
        )

    if screenshot_enabled:
        with tab2:
            for item in items:
                screenshot_path = getattr(item, "screenshot_path", None)
                if screenshot_path:
                    with st.expander(f"🔗 [{item.url}]({item.url})"):
                        if item.title:
                            st.markdown(f"### {item.title}")
                        st.markdown(f"**URL:** [{item.url}]({item.url})")
                        st.markdown(f"**Description:** {item.description or '_No description_'}")
                        st.image(screenshot_path, width=500)
