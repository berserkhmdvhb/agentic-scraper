from __future__ import annotations

import time
from typing import Any, Self

import pytest
import streamlit as st

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_JOB_FAILED,
    MSG_INFO_JOB_CANCELED,
    MSG_INFO_NO_VALID_URLS,
)
from agentic_scraper.backend.config.types import AgentMode, OpenAIModel
from agentic_scraper.frontend import ui_runner_helpers as urh
from agentic_scraper.frontend.models import PipelineConfig

# ------------------------ constants to avoid "magic numbers" ------------------

FETCH_CONCURRENCY = 3
LLM_CONCURRENCY = 2
LLM_SCHEMA_RETRIES = 1
RETRY_ATTEMPTS = 2

URL_A = "https://github.com/owner/repo"
URL_B = "https://medium.com/article"
URL_DUP = URL_A
URL_BAD = "notaurl"

EXPECTED_VALID_ITEMS = 3
EXPECTED_SKIPPED = 3
EXPECTED_DURATION = 1.25


def _pipeline_config(
    model: OpenAIModel | None = OpenAIModel.GPT_4O,
) -> PipelineConfig:
    """
    Build a minimal PipelineConfig for tests.
    """
    return PipelineConfig(
        fetch_concurrency=FETCH_CONCURRENCY,
        llm_concurrency=LLM_CONCURRENCY,
        screenshot_enabled=False,
        verbose=False,
        openai_model=model,
        agent_mode=AgentMode.LLM_DYNAMIC_ADAPTIVE,
        retry_attempts=RETRY_ATTEMPTS,
        llm_schema_retries=LLM_SCHEMA_RETRIES,
    )


# ------------------------------- validate/dedupe ------------------------------


def test_validate_and_deduplicate_urls_mixes_valid_and_invalid() -> None:
    raw = f"""
{URL_A}
{URL_DUP}
{URL_BAD}
{URL_B}
"""
    valid, invalid = urh.validate_and_deduplicate_urls(raw)
    # Deduped order should preserve first occurrence
    assert valid == [URL_A, URL_B]
    assert URL_BAD in invalid
    # Should not list valid URLs as invalid
    assert URL_A not in invalid
    assert URL_B not in invalid


# ---------------------------------- icons ------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/owner/repo", "💻"),
        ("https://medium.com/article", "✍️"),
        ("https://wikipedia.org/wiki/Test", "📚"),
        ("https://unknown.example", "🔗"),
    ],
)
def test_extract_domain_icon(url: str, expected: str) -> None:
    assert urh.extract_domain_icon(url) == expected


# ------------------------------ valid/invalid UI ------------------------------


def test_render_valid_url_feedback_sets_session_and_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    infos: list[str] = []

    def _info(msg: str) -> None:
        infos.append(msg)

    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner_helpers.st.info",
        _info,
        raising=True,
    )

    # Empty -> warning path
    warnings: list[str] = []

    def _warn(msg: str) -> None:
        warnings.append(msg)

    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner_helpers.st.warning",
        _warn,
        raising=True,
    )
    urh.render_valid_url_feedback([])
    assert warnings
    assert MSG_INFO_NO_VALID_URLS in warnings[-1]

    # Non-empty -> info and session_state.valid_urls gets set
    urls = [URL_A, URL_B]
    urh.render_valid_url_feedback(urls)
    assert st.session_state.get("valid_urls") == urls
    assert infos  # at least one info emitted


def test_render_invalid_url_section_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    # Capture lines written by the function
    rendered: list[str] = []

    class DummyExpander:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

    def _markdown(s: str) -> None:
        rendered.append(s)

    # Patch the expander context and markdown call used inside the function
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner_helpers.st.expander",
        lambda *_a, **_k: DummyExpander(),
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner_helpers.st.markdown",
        _markdown,
        raising=True,
    )

    urh.render_invalid_url_section([URL_BAD])

    # Ensure at least one line includes the invalid URL we passed in
    assert any(URL_BAD in line for line in rendered)


# ------------------------------ attach_openai_config --------------------------


def test_attach_openai_config_attaches_inline_creds_and_llm_fields() -> None:
    # Provide inline creds in session_state
    st.session_state.clear()
    st.session_state["openai_credentials"] = {"api_key": "sk-live-xyz", "project": "p1"}

    body: dict[str, Any] = {}
    cfg = _pipeline_config()
    ok = urh.attach_openai_config(cfg, body)

    assert ok is True
    # Inline creds attached
    assert "openai_credentials" in body
    assert body["openai_credentials"]["api_key"] == "sk-live-xyz"
    # LLM fields attached
    assert body["openai_model"] == OpenAIModel.GPT_4O.value
    assert body["llm_concurrency"] == LLM_CONCURRENCY
    assert body["llm_schema_retries"] == LLM_SCHEMA_RETRIES


def test_attach_openai_config_masks_block_inline_creds() -> None:
    # Masked values should not be attached
    st.session_state.clear()
    st.session_state["openai_credentials"] = {"api_key": "sk-****", "project": "p1"}

    body: dict[str, Any] = {}
    cfg = _pipeline_config()
    _ = urh.attach_openai_config(cfg, body)

    assert "openai_credentials" not in body
    # But optional LLM fields still attach
    assert "openai_model" in body
    assert "llm_concurrency" in body
    assert "llm_schema_retries" in body


def test_attach_openai_config_accepts_model_dump_objects() -> None:
    # Simulate a Pydantic v2 object with .model_dump()
    class Creds:
        def __init__(self, api_key: str, project: str) -> None:
            self.api_key = api_key
            self.project = project

        def model_dump(self) -> dict[str, str]:
            return {"api_key": self.api_key, "project": self.project}

    st.session_state.clear()
    st.session_state["openai_credentials"] = Creds("sk-live-abc", "p2")

    body: dict[str, Any] = {}
    cfg = _pipeline_config()
    _ = urh.attach_openai_config(cfg, body)

    assert "openai_credentials" in body
    assert body["openai_credentials"]["project"] == "p2"


# -------------------------------- summarize_results ---------------------------


def test_summarize_results_no_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ensure it shows a warning without raising
    warnings: list[str] = []

    def _warn(msg: str) -> None:
        warnings.append(msg)

    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner_helpers.st.warning",
        _warn,
        raising=True,
    )
    urh.summarize_results([], skipped=1, start_time=time.perf_counter())
    assert warnings  # at least one warning emitted


def test_summarize_results_with_items_smoke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Replace st.columns + st.expander to avoid real UI calls
    class DummyCols:
        def metric(self, _label: str, _value: str) -> None:
            return None

    def _columns(_n: int) -> tuple[DummyCols, DummyCols, DummyCols]:
        return DummyCols(), DummyCols(), DummyCols()

    class DummyExpander:
        def __enter__(self) -> Self:
            return self

        def __exit__(
            self,
            exc_type: object,
            exc: object,
            tb: object,
        ) -> None:
            return None

        def markdown(self, _s: str) -> None:
            return None

    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner_helpers.st.columns",
        _columns,
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner_helpers.st.expander",
        lambda *_a, **_k: DummyExpander(),
        raising=True,
    )
    # smoke: should not raise
    urh.summarize_results(
        [{"url": URL_A, "title": "Repo"}, {"url": URL_B, "title": "Article"}],
        skipped=0,
        start_time=time.perf_counter(),
    )


# -------------------------------- parse_job_result ----------------------------


def test_parse_job_result_handles_dicts_models_and_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pydantic-like v2 object
    class V2Obj:
        def __init__(self, url: str) -> None:
            self._url = url

        def model_dump(self) -> dict[str, str]:
            return {"url": self._url, "title": "v2"}

    # Pydantic-like v1 object
    class V1Obj:
        def __init__(self, url: str) -> None:
            self._url = url

        def dict(self) -> dict[str, str]:
            return {"url": self._url, "title": "v1"}

    # Capture warnings pushed to Streamlit
    warns: list[str] = []

    def _warn(msg: str) -> None:
        warns.append(str(msg))

    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner_helpers.st.warning",
        _warn,
        raising=True,
    )

    job = {
        "status": "succeeded",
        "result": {
            "items": [
                {"url": URL_A, "title": "dict"},
                V2Obj(URL_B),
                V1Obj("https://wikipedia.org/wiki/X"),
                42,  # malformed
            ],
            "stats": {
                "num_failed": EXPECTED_SKIPPED,
                "duration_sec": EXPECTED_DURATION,
            },
        },
    }

    items, skipped, duration = urh.parse_job_result(job)
    # Three valid items (dict + v2 + v1), one malformed skipped
    assert len(items) == EXPECTED_VALID_ITEMS
    assert skipped == EXPECTED_SKIPPED
    assert duration == EXPECTED_DURATION
    assert any("Skipped" in m for m in warns)


# -------------------------------- render_job_error ----------------------------


def test_render_job_error_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    infos: list[str] = []
    errors: list[str] = []

    def _info(msg: str) -> None:
        infos.append(msg)

    def _err(msg: str) -> None:
        errors.append(msg)

    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner_helpers.st.info",
        _info,
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner_helpers.st.error",
        _err,
        raising=True,
    )

    urh.render_job_error({"status": "canceled"})
    assert infos
    assert MSG_INFO_JOB_CANCELED in infos[0]

    urh.render_job_error({"status": "succeeded", "error": {"message": "boom"}})
    assert errors
    assert "boom" in errors[-1]

    urh.render_job_error({"status": "failed", "error": None})
    assert errors
    assert errors[-1] == MSG_ERROR_JOB_FAILED
