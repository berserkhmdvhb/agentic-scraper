from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from agentic_scraper.frontend import ui_page_config as upc

if TYPE_CHECKING:
    # Only needed for typing; runtime import is handled by the fixture skip
    from streamlit.testing.v1 import AppTest


# ----------------------- configure_page (smoke) ------------------------------


def test_configure_page_smoke() -> None:
    """
    Public API smoke test: ensure configure_page renders without raising.
    We don't assert on logo here to avoid touching private helpers.
    """
    upc.configure_page()


# ----------------------- render_input_section (AppTest) ----------------------


@pytest.mark.usefixtures("streamlit_app_test")
def test_render_input_section_paste_urls(
    streamlit_app_test: Callable[[str], object],
    tmp_path: Path,
) -> None:
    # Build a tiny app file that uses the functions under test and stores the value
    app_code = """
import streamlit as st
from agentic_scraper.frontend.ui_page_config import configure_page, render_input_section

configure_page()
raw = render_input_section()
st.session_state["raw_urls"] = raw
"""
    app_file = tmp_path / "mini_app_paste.py"
    app_file.write_text(app_code, encoding="utf-8")

    at = cast("AppTest", streamlit_app_test(str(app_file)))
    at.run()

    # Select Paste URLs and fill text area
    at.text_area[0].set_value("https://a.com\nhttps://b.com")
    at.run()

    # Assert on session state (stable across reruns)
    assert at.session_state["raw_urls"] == "https://a.com\nhttps://b.com"


# ----------------------- render_input_section (unit: upload + decode error) --


def test_render_input_section_upload_and_decode_error_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Unit-level test that simulates the Upload path and a UnicodeDecodeError
    by monkeypatching Streamlit widgets directly within the module under test.
    """
    # Force radio to choose the upload path (patch the name used inside the module)
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_page_config.st.radio",
        lambda *_a, **_k: "Upload .txt file",
        raising=True,
    )

    class DummyUpload:
        def read(self) -> bytes:
            # invalid UTF-8 to trigger UnicodeDecodeError
            return b"\xff\xfe"

    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_page_config.st.file_uploader",
        lambda *_a, **_k: DummyUpload(),
        raising=True,
    )

    errors: list[str] = []

    def _err(msg: str) -> None:
        errors.append(msg)

    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_page_config.st.error",
        _err,
        raising=True,
    )

    out = upc.render_input_section()
    assert out == ""
    assert any("Unable to decode file" in m for m in errors)
