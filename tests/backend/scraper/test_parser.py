from __future__ import annotations

from typing import Any

import pytest
from bs4 import BeautifulSoup

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_PARSED_AUTHOR,
    MSG_DEBUG_PARSED_META_DESCRIPTION,
    MSG_DEBUG_PARSED_TITLE,
    MSG_INFO_NO_AUTHOR,
    MSG_INFO_NO_META_DESCRIPTION,
    MSG_INFO_NO_TITLE,
)
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper import parser as parser_mod

TEST_FERNET_KEY = "A"*43 + "="

def _settings(**overrides: object) -> Settings:
    from agentic_scraper.backend.core.settings import Settings
    base = Settings.model_validate({
        # provide required fields minimally; tests may override
        "AUTH0_DOMAIN": "x",
        "AUTH0_ISSUER": "https://x/",
        "AUTH0_CLIENT_ID": "x",
        "AUTH0_CLIENT_SECRET": "x",
        "AUTH0_API_AUDIENCE": "x",
        "ENV": "PROD",
        "ENCRYPTION_SECRET": TEST_FERNET_KEY,
        "BACKEND_DOMAIN": "http://x",
        "FRONTEND_DOMAIN": "http://x",
        "AUTH0_REDIRECT_URI": "http://x/cb",
    })
    return base.model_copy(update={"verbose": False, **overrides})


def test_extract_main_text_strips_scripts_and_normalizes_whitespace() -> None:
    html = """
    <html>
      <head><title>ignored title</title><style>body { color: red; }</style></head>
      <body>
        <script>console.log('x')</script>
        <noscript>noscript content</noscript>
        <div> Line 1 </div>
        <div>   Line 2</div>
        <div>Line 3</div>
      </body>
    </html>
    """
    text = parser_mod.extract_main_text(html)
    # newline preserved, no script/style/noscript, no extra blanks
    assert text.splitlines() == ["ignored title", "Line 1", "Line 2", "Line 3"]

@pytest.mark.parametrize(("html", "expected"), [
    ("<html><head><title> Hello </title></head><body></body></html>", "Hello"),
    ("<html><head></head><body></body></html>", None),
])
def test_extract_title_logging(html: str, expected: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
    settings_verbose = _settings(verbose=True)
    settings_quiet = _settings(verbose=False)

    # --- Intercept logger calls directly to avoid handler/propagation differences ---
    logged: dict[str, list[str]] = {"debug": [], "info": []}

    def fake_debug(msg: str, *args: Any, **kwargs: Any) -> None:
        # mimic logging’s %-formatting if someone passed args (we don't here, but safe)
        logged["debug"].append(msg if not args else msg % args)

    def fake_info(msg: str, *args: Any, **kwargs: Any) -> None:
        logged["info"].append(msg if not args else msg % args)

    monkeypatch.setattr(parser_mod.logger, "debug", fake_debug, raising=True)
    monkeypatch.setattr(parser_mod.logger, "info", fake_info, raising=True)

    # ---- verbose path ----
    out_v = parser_mod.extract_title_from_soup(BeautifulSoup(html, "html.parser"), settings_verbose)
    assert out_v == expected

    if expected is not None:
        prefix = MSG_DEBUG_PARSED_TITLE.split("{", 1)[0]
        assert any(m.startswith(prefix) and expected in m for m in logged["debug"])
        # Should not have emitted the "no title" info when a title exists
        assert not any(MSG_INFO_NO_TITLE.split("{", 1)[0] in m for m in logged["info"])
    else:
        assert any(MSG_INFO_NO_TITLE.split("{", 1)[0] in m for m in logged["info"])
        # No debug title log when missing
        prefix = MSG_DEBUG_PARSED_TITLE.split("{", 1)[0]
        assert not any(m.startswith(prefix) for m in logged["debug"])

    # ---- quiet path: no debug even if title exists ----
    logged["debug"].clear()
    logged["info"].clear()
    out_q = parser_mod.extract_title_from_soup(BeautifulSoup(html, "html.parser"), settings_quiet)
    assert out_q == expected

    prefix = MSG_DEBUG_PARSED_TITLE.split("{", 1)[0]
    assert not any(m.startswith(prefix) for m in logged["debug"])

@pytest.mark.parametrize(
    ("meta_attrs", "content", "expected"),
    [
        ({"name": "description"}, "This is a summary.", "This is a summary."),
        ({"property": "og:description"}, "ignored", None),  # not parsed by current code
        ({}, "", None),
    ],
)
def test_extract_meta_description_logging(
    meta_attrs: dict[str, str],
    content: str,
    expected: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if meta_attrs:
        # Build attribute string outside the f-string to avoid backslashes in expressions
        # (required for Python < 3.12 where f-strings disallow backslashes in expr parts).
        attrs = " ".join(f'{k}="{v}"' for k, v in meta_attrs.items())
        html = f"<html><head><meta {attrs} content='{content}'></head></html>"
    else:
        html = "<html><head></head></html>"

    soup = BeautifulSoup(html, "html.parser")
    settings_verbose = _settings(verbose=True)
    settings_quiet = _settings(verbose=False)

    # Patch logger (avoid caplog flakiness)
    logged: dict[str, list[str]] = {"debug": [], "info": []}

    def fake_debug(msg: str, *args: Any, **kwargs: Any) -> None:
        logged["debug"].append(msg if not args else msg % args)

    def fake_info(msg: str, *args: Any, **kwargs: Any) -> None:
        logged["info"].append(msg if not args else msg % args)

    monkeypatch.setattr(parser_mod.logger, "debug", fake_debug, raising=True)
    monkeypatch.setattr(parser_mod.logger, "info", fake_info, raising=True)

    # Verbose path
    out_v = parser_mod.extract_meta_description_from_soup(soup, settings_verbose)
    assert out_v == expected
    if expected is not None:
        prefix = MSG_DEBUG_PARSED_META_DESCRIPTION.split("{", 1)[0]
        assert any(m.startswith(prefix) and expected in m for m in logged["debug"])
        assert not any(MSG_INFO_NO_META_DESCRIPTION in m for m in logged["info"])
    else:
        assert any(MSG_INFO_NO_META_DESCRIPTION in m for m in logged["info"])
        prefix = MSG_DEBUG_PARSED_META_DESCRIPTION.split("{", 1)[0]
        assert not any(m.startswith(prefix) for m in logged["debug"])
    # Quiet path
    logged["debug"].clear()
    logged["info"].clear()
    out_q = parser_mod.extract_meta_description_from_soup(soup, settings_quiet)
    assert out_q == expected
    prefix = MSG_DEBUG_PARSED_META_DESCRIPTION.split("{", 1)[0]
    assert not any(m.startswith(prefix) for m in logged["debug"])
    if expected is None:
        assert any(MSG_INFO_NO_META_DESCRIPTION in m for m in logged["info"])

@pytest.mark.parametrize(
    ("meta_html", "expected_source_key", "expected_value"),
    [
        ('<meta name="author" content="Alice">', "name", "Alice"),
        ('<meta property="article:author" content="Bob">', "property", "Bob"),
        ('<meta name="byline" content="Carol">', "name", "Carol"),
        ("", None, None),
    ],
)
def test_extract_author_logging(
    meta_html: str,
    expected_source_key: str | None,
    expected_value: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = f"<html><head>{meta_html}</head></html>"
    soup = BeautifulSoup(html, "html.parser")
    settings_verbose = _settings(verbose=True)
    settings_quiet = _settings(verbose=False)

    # Patch logger (avoid caplog flakiness)
    logged: dict[str, list[str]] = {"debug": [], "info": []}

    def fake_debug(msg: str, *args: Any, **kwargs: Any) -> None:
        logged["debug"].append(msg if not args else msg % args)

    def fake_info(msg: str, *args: Any, **kwargs: Any) -> None:
        logged["info"].append(msg if not args else msg % args)

    monkeypatch.setattr(parser_mod.logger, "debug", fake_debug, raising=True)
    monkeypatch.setattr(parser_mod.logger, "info", fake_info, raising=True)

    # Verbose path
    out_v = parser_mod.extract_author_from_soup(soup, settings_verbose)
    assert out_v == expected_value
    if expected_value is not None:
        prefix = MSG_DEBUG_PARSED_AUTHOR.split("{", 1)[0]
        assert any(m.startswith(prefix) and expected_value in m for m in logged["debug"])
        assert not any(MSG_INFO_NO_AUTHOR in m for m in logged["info"])
    else:
        assert any(MSG_INFO_NO_AUTHOR in m for m in logged["info"])
        prefix = MSG_DEBUG_PARSED_AUTHOR.split("{", 1)[0]
        assert not any(m.startswith(prefix) for m in logged["debug"])
    # Quiet path
    logged["debug"].clear()
    logged["info"].clear()
    out_q = parser_mod.extract_author_from_soup(soup, settings_quiet)
    assert out_q == expected_value
    prefix = MSG_DEBUG_PARSED_AUTHOR.split("{", 1)[0]
    assert not any(m.startswith(prefix) for m in logged["debug"])
    if expected_value is None:
        assert any(MSG_INFO_NO_AUTHOR in m for m in logged["info"])

def test_parse_all_metadata_roundtrip() -> None:
    html = """
    <html>
      <head>
        <title>Sample Title</title>
        <meta name="description" content="Short summary here.">
        <meta name="author" content="Dana">
      </head>
      <body><p>Body text</p></body>
    </html>
    """
    settings = _settings(verbose=True)
    meta = parser_mod.parse_all_metadata(html, settings)

    assert meta["title"] == "Sample Title"
    assert meta["description"] == "Short summary here."
    assert meta["author"] == "Dana"
