from __future__ import annotations

import sqlite3
from io import BytesIO
from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st
from typing_extensions import Self

import agentic_scraper.frontend.ui_display as udisp

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

# Small constants for clarity / avoid magic numbers (PLR2004)
NUM_DOWNLOAD_BTNS = 3
NUM_EXPANDERS = 2


# ----------------------------- prepare_dataframe (column order) -----------------------------


def test_prepare_dataframe_orders_columns_and_hides_screenshot() -> None:
    items = [
        {
            "title": "T",
            "url": "http://a",
            "screenshot_path": "a.png",
            "extra": 1,
        },
        {
            "title": "U",
            "url": "http://b",
            "screenshot_path": "b.png",
            "extra": 2,
        },
    ]

    # When disabled, the screenshot column should be removed and URL first
    df = udisp.prepare_dataframe(items, screenshot_enabled=False)
    assert "screenshot_path" not in df.columns
    assert next(iter(df.columns)) == "url"

    # When enabled, the screenshot column remains and is last
    df2 = udisp.prepare_dataframe(items, screenshot_enabled=True)
    assert "screenshot_path" in df2.columns
    assert df2.columns[-1] == "screenshot_path"
    assert df2.columns[0] == "url"


# ----------------------------- dataframe_to_sqlite_bytes -----------------------------


def test_dataframe_to_sqlite_bytes_roundtrip() -> None:
    df = pd.DataFrame(
        [
            {"url": "http://x", "title": "A", "tags": ["t1", "t2"]},
            {"url": "http://y", "title": "B", "meta": {"k": "v"}},
        ]
    )
    buf = udisp.dataframe_to_sqlite_bytes(df)
    assert isinstance(buf, BytesIO)
    data = buf.getvalue()
    assert len(data) > 0
    assert b"CREATE TABLE" in data


# ----------------------------- display_results (table-only branch) -----------------------------


def test_display_results_table_only_downloads(monkeypatch: MonkeyPatch) -> None:
    items = [{"url": "http://a", "title": "X"}, {"url": "http://b", "title": "Y"}]

    calls = {"table": 0}
    dls = {"n": 0}

    def _dataframe(_df: pd.DataFrame, **_: object) -> None:
        calls["table"] += 1

    class _Tab:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object, **_kwargs: object) -> None:
            return None

    def _tabs(_labels: list[str]) -> tuple[_Tab]:
        return (_Tab(),)

    def _cols(_sizes: list[int]) -> tuple[object, object, object]:
        class _C:
            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_: object, **__: object) -> None:
                return None

        return _C(), _C(), _C()

    def _download_button(*_args: object, **_kwargs: object) -> None:
        dls["n"] += 1

    # Avoid AgGrid rendering (UI)
    monkeypatch.setattr(udisp, "display_data_table", _dataframe, raising=True)
    monkeypatch.setattr(st, "tabs", _tabs, raising=True)
    monkeypatch.setattr(st, "columns", _cols, raising=True)
    monkeypatch.setattr(st, "download_button", _download_button, raising=True)

    udisp.display_results(items, job_id="J1", screenshot_enabled=False)

    # Table rendered and 3 download buttons shown (JSON/CSV/SQLite)
    assert calls["table"] == 1
    assert dls["n"] == NUM_DOWNLOAD_BTNS


def test_display_results_sqlite_error_shows_error(monkeypatch: MonkeyPatch) -> None:
    items = [{"url": "http://a", "title": "X"}]

    errs: list[str] = []
    dls = {"n": 0}

    class _Tab:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object, **_kwargs: object) -> None:
            return None

    def _tabs(_labels: list[str]) -> tuple[_Tab]:
        return (_Tab(),)

    def _cols(_sizes: list[int]) -> tuple[object, object, object]:
        class _C:
            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_: object, **__: object) -> None:
                return None

        return _C(), _C(), _C()

    def _download_button(*_args: object, **_kwargs: object) -> None:
        dls["n"] += 1

    def _df_to_sqlite(_df: pd.DataFrame, table_name: str = "scraped_data") -> BytesIO:
        _ = table_name, _df
        msg = "boom"
        raise sqlite3.OperationalError(msg)

    monkeypatch.setattr(udisp, "display_data_table", lambda _df: None, raising=True)
    monkeypatch.setattr(st, "tabs", _tabs, raising=True)
    monkeypatch.setattr(st, "columns", _cols, raising=True)
    monkeypatch.setattr(st, "download_button", _download_button, raising=True)
    monkeypatch.setattr(st, "error", lambda m: errs.append(str(m)), raising=True)
    monkeypatch.setattr(udisp, "dataframe_to_sqlite_bytes", _df_to_sqlite, raising=True)

    udisp.display_results(items, job_id="JX", screenshot_enabled=False)

    # Error surfaced but JSON/CSV buttons still rendered
    assert any("Failed to generate SQLite export" in e for e in errs)
    assert dls["n"] == NUM_DOWNLOAD_BTNS


# ----------------------------- display_results (screenshots tab) -----------------------------


def test_display_results_with_screenshots(monkeypatch: MonkeyPatch) -> None:
    items = [
        {
            "url": "http://a",
            "title": "A",
            "description": "da",
            "screenshot_path": "a.png",
        },
        {
            "url": "http://b",
            "title": "B",
            "description": "db",
            "screenshot_path": "b.png",
        },
    ]

    class _Tab:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object, **_kwargs: object) -> None:
            return None

    def _tabs(_labels: list[str]) -> tuple[_Tab, _Tab]:
        return _Tab(), _Tab()

    # Track expanders & images
    expanders: list[str] = []
    images: list[str] = []
    marks: list[str] = []

    class _Exp:
        def __init__(self, label: str) -> None:
            self.label = label

        def __enter__(self) -> Self:
            expanders.append(self.label)
            return self

        def __exit__(self, *_a: object, **_k: object) -> None:
            return None

    def _expander(label: str) -> _Exp:
        return _Exp(label)

    def _markdown(text: str, **_k: object) -> None:
        marks.append(text)

    def _image(path: str, **_k: object) -> None:
        images.append(path)

    # Avoid AgGrid rendering (UI)
    monkeypatch.setattr(udisp, "display_data_table", lambda _df: None, raising=True)
    monkeypatch.setattr(st, "tabs", _tabs, raising=True)
    monkeypatch.setattr(st, "expander", _expander, raising=True)
    monkeypatch.setattr(st, "markdown", _markdown, raising=True)
    monkeypatch.setattr(st, "image", _image, raising=True)

    udisp.display_results(items, job_id="J2", screenshot_enabled=True)

    # Two expanders created, two images rendered
    assert len(expanders) == NUM_EXPANDERS
    assert images == ["a.png", "b.png"]
