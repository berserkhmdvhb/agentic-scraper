"""
Display and export scraped results in the Streamlit frontend.

Responsibilities:
- Convert heterogeneous scrape results (dicts or Pydantic models) into a DataFrame.
- Render an interactive table (AgGrid) with safe defaults and stable column ordering.
- Provide multiple export formats (JSON, CSV, SQLite) with defensive fallbacks.
- Optionally render per-item screenshot details behind expanders.

Public API:
- `prepare_dataframe`: Normalize items → `pd.DataFrame` with stable columns.
- `display_data_table`: Render the DataFrame via AgGrid with sane defaults.
- `display_results`: High-level UI that shows tables, exports, and screenshots.
- `dataframe_to_sqlite_bytes`: Serialize a DataFrame into an in-memory SQLite DB.

Operational:
- Robustness: Avoids AgGrid config for missing columns; handles empty data gracefully.
- Column order: `"url"` first and `"screenshot_path"` last when present.
- Exports: SQLite export serializes lists/dicts as JSON strings for portability.

Usage:
    df = prepare_dataframe(items, screenshot_enabled=True)
    display_data_table(df)  # or
    display_results(items, job_id="abc123", screenshot_enabled=True)

Notes:
- The interactive grid is best-effort; empty DataFrames show a friendly message instead.
- Screenshots are shown only when `screenshot_enabled=True` and paths are present.
"""

from __future__ import annotations

import json
import sqlite3
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from pydantic import HttpUrl
from st_aggrid import AgGrid, GridOptionsBuilder

__all__ = [
    "dataframe_to_sqlite_bytes",
    "display_data_table",
    "display_results",
    "prepare_dataframe",
]


def dataframe_to_sqlite_bytes(df: pd.DataFrame, table_name: str = "scraped_data") -> BytesIO:
    """
    Convert a DataFrame into an in-memory SQLite database and return it as bytes.

    The function copies and serializes JSON-like values so they round-trip in SQLite:
    - `list`/`dict` values → JSON strings
    - `HttpUrl`/`Path` → string paths

    Args:
        df (pd.DataFrame): Input DataFrame to serialize.
        table_name (str): Table name to create in the SQLite dump.

    Returns:
        BytesIO: A buffer containing the SQLite dump (plain-text `iterdump` format).

    Examples:
        sqlite_bytes = dataframe_to_sqlite_bytes(df, "results")
        st.download_button("Download .sqlite", sqlite_bytes.getvalue(), "results.sqlite")

    Notes:
        - Uses `:memory:` then `iterdump()` to produce the portable bytes.
        - Column types are inferred by pandas/SQLite after serialization.
    """
    buffer = BytesIO()
    df_serialized = df.copy()

    def safe_serialize(x: object) -> str | object:
        if isinstance(x, (list, dict)):
            return json.dumps(x)
        if isinstance(x, (HttpUrl, Path)):
            return str(x)
        return x

    # Apply serialization only when there is data
    if not df_serialized.empty:
        for col in df_serialized.columns:
            df_serialized[col] = df_serialized[col].apply(safe_serialize)

    with sqlite3.connect(":memory:") as conn:
        df_serialized.to_sql(table_name, conn, index=False, if_exists="replace")
        # Use iterdump to produce a single-file SQL dump; broadly compatible.
        for line in conn.iterdump():
            buffer.write(f"{line}\n".encode())

    buffer.seek(0)
    return buffer


def _stable_column_order(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a view of `df` with `'url'` first and `'screenshot_path'` last when present.

    Args:
        df (pd.DataFrame): Input DataFrame.

    Returns:
        pd.DataFrame: Reordered view of the input.
    """
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


def prepare_dataframe(items: list[Any], *, screenshot_enabled: bool) -> pd.DataFrame:
    """
    Convert scraped items (dicts or models) into a cleaned and stably-ordered DataFrame.

    Rules:
        - Prefers `dict` inputs to preserve dynamic/extra fields unmodified.
        - For Pydantic objects, uses `model_dump()` (v2) or `dict()` (v1).
        - Ensures `'url'` exists and is a string.
        - Drops `'screenshot_path'` when `screenshot_enabled=False`.

    Args:
        items (list[Any]): Extracted items—each either a dict or a Pydantic model.
        screenshot_enabled (bool): Whether to keep the screenshot column.

    Returns:
        pd.DataFrame: Normalized results table (may be empty).

    Examples:
        df = prepare_dataframe(items, screenshot_enabled=True)
        st.dataframe(df)
    """
    if not items:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for it in items:
        # Prefer dicts to preserve dynamic extras
        if isinstance(it, dict):
            url = str(it.get("url", ""))
            row = dict(it)
            row["url"] = url  # ensure string URL (and ensure column exists)
            rows.append(row)
            continue

        # Pydantic model (v2 or v1) fallback
        try:
            if hasattr(it, "model_dump"):
                data = it.model_dump()
            elif hasattr(it, "dict"):
                data = it.dict()
            else:
                data = {}
        except (AttributeError, TypeError, ValueError):
            data = {}
        data["url"] = str(getattr(it, "url", data.get("url", "")))
        rows.append(data)

    df_extracted = pd.DataFrame(rows)

    # Optionally hide screenshots entirely for speed/simplicity
    if not screenshot_enabled and "screenshot_path" in df_extracted.columns:
        df_extracted = df_extracted.drop(columns=["screenshot_path"])

    return _stable_column_order(df_extracted)


def display_data_table(df: pd.DataFrame) -> None:
    """
    Render the extracted data using an interactive AgGrid table.

    Args:
        df (pd.DataFrame): DataFrame to render.

    Returns:
        None

    Notes:
        - Empty data shows a friendly message instead of an empty grid.
        - `screenshot_path` is kept as a hidden column to preserve exports while avoiding clutter.
    """
    if df.empty:
        st.info("No rows to display yet.")
        return

    gb = GridOptionsBuilder.from_dataframe(df)
    if "screenshot_path" in df.columns:
        gb.configure_column("screenshot_path", hide=True)  # keep column but hidden
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_default_column(filter=True, sortable=True, resizable=True)
    grid_options = gb.build()

    # `fit_columns_on_grid_load=True` improves initial readability for wide, mixed-type tables.
    AgGrid(
        df,
        gridOptions=grid_options,
        enable_enterprise_modules=False,
        fit_columns_on_grid_load=True,
        theme="streamlit",
    )


def display_results(
    items: list[Any],
    job_id: str | None = None,
    *,
    screenshot_enabled: bool,
) -> None:
    """
    Display extracted results with an interactive table, export buttons, and screenshots.

    Args:
        items (list[Any]): Extracted items from the backend.
        job_id (str | None): Optional job id used for export filenames.
        screenshot_enabled (bool): Whether to include screenshot details.

    Returns:
        None

    Notes:
        - Stores the current DataFrame in `st.session_state["results_df"]` for reuse.
        - Export buttons provide JSON, CSV, and SQLite formats (with robust error handling).
        - Screenshots render under a separate tab (when enabled).
    """
    df_extracted = prepare_dataframe(items, screenshot_enabled=screenshot_enabled)
    st.session_state.results_df = df_extracted

    if df_extracted.empty:
        st.info("Nothing to show yet. Try running a scrape or adjust your filters.")
        return

    # Tabs: show a dedicated screenshot view only when enabled
    if screenshot_enabled:
        tab1, tab2 = st.tabs(["📋 Extracted Table", "🖼️ Screenshot Details"])
    else:
        (tab1,) = st.tabs(["📋 Table Preview"])

    with tab1:
        display_data_table(df_extracted)

        # Compose filenames with job_id for clarity and traceability
        file_prefix = f"scrape_{job_id}" if job_id else "results"

        # Compact, single-row export toolbar
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button(
                "Export table (JSON)",
                df_extracted.to_json(orient="records", indent=2),
                f"{file_prefix}_results.json",
                mime="application/json",
                help="Only the rows shown in the results table.",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "Export table (CSV)",
                df_extracted.to_csv(index=False),
                f"{file_prefix}_results.csv",
                mime="text/csv",
                help="Only the rows shown in the results table.",
                use_container_width=True,
            )
        with c3:
            try:
                sqlite_bytes = dataframe_to_sqlite_bytes(df_extracted)
            except (sqlite3.Error, ValueError, TypeError) as e:
                # Keep the UI responsive even if SQLite export fails
                st.error(f"❌ Failed to generate SQLite export: {e}")
                sqlite_bytes = BytesIO()
            st.download_button(
                "Export table (SQLite)",
                data=sqlite_bytes,
                file_name=f"{file_prefix}_results.sqlite",
                mime="application/x-sqlite3",
                help="Only the rows shown in the results table.",
                use_container_width=True,
            )

    if screenshot_enabled:
        with tab2:
            # Render per-item screenshot blocks with minimal assumptions about shape
            for it in items:
                # dict-safe attribute access
                if isinstance(it, dict):
                    url = it.get("url")
                    title = it.get("title")
                    description = it.get("description")
                    screenshot_path = it.get("screenshot_path")
                else:
                    url = getattr(it, "url", None)
                    title = getattr(it, "title", None)
                    description = getattr(it, "description", None)
                    screenshot_path = getattr(it, "screenshot_path", None)

                if screenshot_path and url:
                    with st.expander(f"🔗 [{url}]({url})"):
                        if title:
                            st.markdown(f"### {title}")
                        if url:
                            st.markdown(f"**URL:** [{url}]({url})")
                        st.markdown(f"**Description:** {description or '_No description_'}")
                        st.image(screenshot_path, width=500)
