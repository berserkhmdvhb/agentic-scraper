import json
import sqlite3
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from pydantic import HttpUrl
from st_aggrid import AgGrid, GridOptionsBuilder

from agentic_scraper.backend.scraper.models import ScrapedItem


def dataframe_to_sqlite_bytes(df: pd.DataFrame, table_name: str = "scraped_data") -> BytesIO:
    """Convert a DataFrame to a SQLite dump in memory as BytesIO."""
    buffer = BytesIO()
    df_serialized = df.copy()

    def safe_serialize(x: object) -> str | object:
        if isinstance(x, (list, dict)):
            return json.dumps(x)
        if isinstance(x, (HttpUrl, Path)):
            return str(x)
        return x

    for col in df_serialized.columns:
        df_serialized[col] = df_serialized[col].apply(safe_serialize)

    with sqlite3.connect(":memory:") as conn:
        df_serialized.to_sql(table_name, conn, index=False, if_exists="replace")
        for line in conn.iterdump():
            buffer.write(f"{line}\n".encode())

    buffer.seek(0)
    return buffer


def prepare_dataframe(items: list[ScrapedItem], *, screenshot_enabled: bool) -> pd.DataFrame:
    """Prepare and serialize the dataframe with relevant data."""
    df_extracted_data = pd.DataFrame(
        [{**item.model_dump(exclude={"url"}), "url": str(item.url)} for item in items]
    )

    if not screenshot_enabled and "screenshot_path" in df_extracted_data.columns:
        df_extracted_data = df_extracted_data.drop(columns=["screenshot_path"])

    if "screenshot_path" in df_extracted_data.columns:
        cols = [col for col in df_extracted_data.columns if col != "screenshot_path"]
        cols += ["screenshot_path"]

        df_extracted_data = df_extracted_data[cols]


def display_data_table(df: pd.DataFrame) -> None:
    """Display the extracted data table using AgGrid."""
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_column("screenshot_path", hide=True)
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
    """Display scraped results in table and/or screenshot form, with export buttons."""
    st.markdown("### 📊 **Display Results**")

    df_extracted_data = prepare_dataframe(items, screenshot_enabled=screenshot_enabled)

    st.session_state.results_df = df_extracted_data

    # Display Tabs
    if screenshot_enabled:
        tab1, tab2 = st.tabs(["📋 Extracted Table", "🖼️ Screenshot Details"])
    else:
        (tab1,) = st.tabs(["📋 Table Preview"])

    with tab1:
        display_data_table(df_extracted_data)

        # Export options
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

        try:
            sqlite_bytes = dataframe_to_sqlite_bytes(df_extracted_data)
        except (sqlite3.InterfaceError, ValueError, TypeError) as e:
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
                if item.screenshot_path:
                    with st.expander(f"🔗 [{item.url}]({item.url})"):
                        if item.title:
                            st.markdown(f"### {item.title}")
                        st.markdown(f"**URL:** [{item.url}]({item.url})")
                        st.markdown(f"**Description:** {item.description or '_No description_'}")
                        st.image(item.screenshot_path, width=500)
