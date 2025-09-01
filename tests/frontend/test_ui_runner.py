from __future__ import annotations

import json
from collections.abc import Callable
from typing import Protocol

import httpx
import pytest
import streamlit as st
from fastapi import status

from agentic_scraper.backend.config.types import AgentMode, OpenAIModel
from agentic_scraper.frontend import ui_runner as ur
from agentic_scraper.frontend.models import PipelineConfig

BASE = "http://api.example.com/api/v1"
JOB_ID = "job-123"


class RouterProto(Protocol):
    def add_handler(
        self,
        method: str,
        url: str,
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> None: ...

    def add_json(
        self,
        method: str,
        url: str,
        status: int = 200,
        json_data: object | None = None,
        headers: dict[str, str] | None = None,
    ) -> None: ...

    def add_text(
        self,
        method: str,
        url: str,
        status: int = 200,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None: ...


def _cfg(
    agent_mode: AgentMode,
    *,
    model: OpenAIModel | None = OpenAIModel.GPT_4O,
) -> PipelineConfig:
    return PipelineConfig(
        fetch_concurrency=3,
        llm_concurrency=2,
        screenshot_enabled=False,
        verbose=False,
        openai_model=model,
        agent_mode=agent_mode,
        retry_attempts=2,
        llm_schema_retries=1,
    )


# ------------------------ create_scrape_job ------------------------


@pytest.mark.asyncio
async def test_create_scrape_job_llm_mode_attaches_fields(
    monkeypatch: pytest.MonkeyPatch,
    httpx_backend_mock: Callable[[], RouterProto],
    st_session: Callable[[dict[str, object] | None], None],
) -> None:
    st_session(
        {"jwt_token": "token", "openai_credentials": {"api_key": "sk-live-123"}},
    )
    router = httpx_backend_mock()

    posted: list[dict[str, object]] = []

    def _post_handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert str(req.url) == f"{BASE}/scrapes/"
        body = json.loads(req.content.decode("utf-8"))
        posted.append(body)
        return httpx.Response(
            status.HTTP_202_ACCEPTED,
            json={"id": JOB_ID},
            headers={"Location": f"{BASE}/scrapes/{JOB_ID}"},
        )

    router.add_handler("POST", f"{BASE}/scrapes/", _post_handler)
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner._request_base_url",
        lambda: BASE,
        raising=True,
    )

    job_id, location = await ur.create_scrape_job(
        ["https://a.com", "https://b.com"],
        _cfg(AgentMode.LLM_DYNAMIC_ADAPTIVE),
    )

    assert job_id == JOB_ID
    assert location == f"{BASE}/scrapes/{JOB_ID}"
    assert posted, "expected a POST body to be captured"
    body = posted[-1]

    assert body["agent_mode"] == AgentMode.LLM_DYNAMIC_ADAPTIVE
    assert "openai_credentials" in body
    assert "openai_model" in body
    assert "llm_concurrency" in body
    assert "llm_schema_retries" in body


@pytest.mark.asyncio
async def test_create_scrape_job_rule_based_strips_llm_fields(
    monkeypatch: pytest.MonkeyPatch,
    httpx_backend_mock: Callable[[], RouterProto],
    st_session: Callable[[dict[str, object] | None], None],
) -> None:
    st_session(
        {"jwt_token": "token", "openai_credentials": {"api_key": "sk-live-123"}},
    )
    router = httpx_backend_mock()

    captured: dict[str, object] = {}

    def _post_handler(req: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = json.loads(req.content.decode("utf-8"))
        return httpx.Response(status.HTTP_202_ACCEPTED, json={"id": JOB_ID})

    router.add_handler("POST", f"{BASE}/scrapes/", _post_handler)
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner._request_base_url",
        lambda: BASE,
        raising=True,
    )

    _job_id, _loc = await ur.create_scrape_job(
        ["https://a.com"],
        _cfg(AgentMode.RULE_BASED),
    )

    for k in (
        "openai_model",
        "llm_concurrency",
        "llm_schema_retries",
        "openai_credentials",
    ):
        assert k not in captured


@pytest.mark.asyncio
async def test_create_scrape_job_missing_id_raises(
    monkeypatch: pytest.MonkeyPatch,
    httpx_backend_mock: Callable[[], RouterProto],
    st_session: Callable[[dict[str, object] | None], None],
) -> None:
    st_session({"jwt_token": "token"})
    router = httpx_backend_mock()

    router.add_json(
        "POST",
        f"{BASE}/scrapes/",
        status.HTTP_202_ACCEPTED,
        json_data={},
    )
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner._request_base_url",
        lambda: BASE,
        raising=True,
    )

    with pytest.raises(ur.BackendNoJobIdError):
        await ur.create_scrape_job(["https://a.com"], _cfg(AgentMode.RULE_BASED))


@pytest.mark.asyncio
async def test_create_scrape_job_non_202_raises_status_error(
    monkeypatch: pytest.MonkeyPatch,
    httpx_backend_mock: Callable[[], RouterProto],
    st_session: Callable[[dict[str, object] | None], None],
) -> None:
    st_session({"jwt_token": "token"})
    router = httpx_backend_mock()

    router.add_text(
        "POST",
        f"{BASE}/scrapes/",
        status=status.HTTP_400_BAD_REQUEST,
        text="bad",
    )
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner._request_base_url",
        lambda: BASE,
        raising=True,
    )

    with pytest.raises(httpx.HTTPStatusError):
        await ur.create_scrape_job(["https://a.com"], _cfg(AgentMode.RULE_BASED))


# ------------------------ poll_scrape_job ------------------------


@pytest.mark.asyncio
async def test_poll_scrape_job_runs_until_succeeded(
    monkeypatch: pytest.MonkeyPatch,
    httpx_backend_mock: Callable[[], RouterProto],
    st_session: Callable[[dict[str, object] | None], None],
) -> None:
    st_session({"jwt_token": "token"})
    router = httpx_backend_mock()

    calls = {"n": 0}

    def _get_handler(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                status.HTTP_200_OK,
                json={"status": "running", "progress": 10},
            )
        return httpx.Response(
            status.HTTP_200_OK,
            json={
                "status": "succeeded",
                "result": {"items": [{"url": "x"}], "stats": {}},
            },
        )

    router.add_handler("GET", f"{BASE}/scrapes/{JOB_ID}", _get_handler)
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner._request_base_url",
        lambda: BASE,
        raising=True,
    )

    job = await ur.poll_scrape_job(JOB_ID, interval_sec=0.01, max_seconds=0.05)
    assert job["status"] == "succeeded"


@pytest.mark.asyncio
async def test_poll_scrape_job_handles_404_and_403(
    monkeypatch: pytest.MonkeyPatch,
    httpx_backend_mock: Callable[[], RouterProto],
    st_session: Callable[[dict[str, object] | None], None],
) -> None:
    st_session({"jwt_token": "token"})
    router = httpx_backend_mock()

    router.add_text(
        "GET",
        f"{BASE}/scrapes/404",
        status.HTTP_404_NOT_FOUND,
        text="missing",
    )
    router.add_text(
        "GET",
        f"{BASE}/scrapes/403",
        status.HTTP_403_FORBIDDEN,
        text="forbidden",
    )
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner._request_base_url",
        lambda: BASE,
        raising=True,
    )

    job = await ur.poll_scrape_job("404", interval_sec=0.01, max_seconds=0.1)
    assert job["status"] == "failed"
    assert "not found" in str(job["error"]).lower()

    job2 = await ur.poll_scrape_job("403", interval_sec=0.01, max_seconds=0.1)
    assert job2["status"] == "failed"
    assert "forbidden" in str(job2["error"]).lower()


@pytest.mark.asyncio
async def test_poll_scrape_job_times_out(
    monkeypatch: pytest.MonkeyPatch,
    httpx_backend_mock: Callable[[], RouterProto],
    st_session: Callable[[dict[str, object] | None], None],
) -> None:
    st_session({"jwt_token": "token"})
    router = httpx_backend_mock()

    router.add_json(
        "GET",
        f"{BASE}/scrapes/{JOB_ID}",
        status.HTTP_200_OK,
        json_data={"status": "running"},
    )
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner._request_base_url",
        lambda: BASE,
        raising=True,
    )

    job = await ur.poll_scrape_job(JOB_ID, interval_sec=0.01, max_seconds=0.05)
    assert job["status"] == "failed"
    assert "timed out" in str(job["error"]).lower()


# ------------------------ cancel_scrape_job ------------------------


@pytest.mark.asyncio
async def test_cancel_scrape_job_variants(
    monkeypatch: pytest.MonkeyPatch,
    httpx_backend_mock: Callable[[], RouterProto],
    st_session: Callable[[dict[str, object] | None], None],
) -> None:
    st_session({"jwt_token": "token"})
    router = httpx_backend_mock()
    infos: list[str] = []
    errors: list[str] = []

    def _info(msg: str) -> None:
        infos.append(msg)

    def _err(msg: str) -> None:
        errors.append(msg)

    monkeypatch.setattr("agentic_scraper.frontend.ui_runner.st.info", _info, raising=True)
    monkeypatch.setattr("agentic_scraper.frontend.ui_runner.st.error", _err, raising=True)

    router.add_text("DELETE", f"{BASE}/scrapes/ok", status.HTTP_204_NO_CONTENT, text="")
    router.add_text("DELETE", f"{BASE}/scrapes/conflict", status.HTTP_409_CONFLICT, text="")
    router.add_text("DELETE", f"{BASE}/scrapes/bad", status.HTTP_400_BAD_REQUEST, text="bad")

    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner._request_base_url",
        lambda: BASE,
        raising=True,
    )

    assert await ur.cancel_scrape_job("ok") is True
    assert await ur.cancel_scrape_job("conflict") is False
    assert infos, "expected info on 409 conflict"

    assert await ur.cancel_scrape_job("bad") is False
    assert errors
    assert "bad" in errors[-1]


# ------------------------ submit_scrape_job & run_scraper_pipeline ------------------------


def test_submit_scrape_job_success(
    monkeypatch: pytest.MonkeyPatch,
    st_session: Callable[[dict[str, object] | None], None],
) -> None:
    st_session({"jwt_token": "token"})

    async def _fake_create(
        urls: list[str],
        _config: PipelineConfig,
    ) -> tuple[str, str | None]:
        assert urls == ["https://a.com", "https://b.com"]
        return "job-42", None

    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner.validate_and_deduplicate_urls",
        lambda _raw: (["https://a.com", "https://b.com"], []),
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner.create_scrape_job",
        _fake_create,
        raising=True,
    )

    messages: list[str] = []

    def _success(msg: str) -> None:
        messages.append(msg)

    monkeypatch.setattr("agentic_scraper.frontend.ui_runner.st.success", _success, raising=True)

    job_id = ur.submit_scrape_job("https://a.com\nhttps://b.com", _cfg(AgentMode.RULE_BASED))
    assert job_id == "job-42"
    assert st.session_state.get("last_job_id") == "job-42"
    assert messages, "expected a success message"


def test_submit_scrape_job_handles_http_errors(
    monkeypatch: pytest.MonkeyPatch,
    st_session: Callable[[dict[str, object] | None], None],
) -> None:
    st_session({"jwt_token": "token"})

    async def _raise_http(_urls: list[str], _config: PipelineConfig) -> tuple[str, str | None]:
        req = httpx.Request("POST", f"{BASE}/scrapes/")
        resp = httpx.Response(status.HTTP_401_UNAUTHORIZED, request=req)
        msg = "unauth"
        raise httpx.HTTPStatusError(msg, request=req, response=resp)

    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner.validate_and_deduplicate_urls",
        lambda _raw: (["https://a.com"], []),
        raising=True,
    )
    monkeypatch.setattr(
        "agentic_scraper.frontend.ui_runner.create_scrape_job",
        _raise_http,
        raising=True,
    )

    infos: list[str] = []

    def _info(msg: str) -> None:
        infos.append(msg)

    monkeypatch.setattr("agentic_scraper.frontend.ui_runner.st.info", _info, raising=True)

    job_id = ur.submit_scrape_job("https://a.com", _cfg(AgentMode.RULE_BASED))
    assert job_id is None
    assert "jwt_token" not in st.session_state
    assert infos, "expected login info prompt"


def test_run_scraper_pipeline_non_blocking(
    st_session: Callable[[dict[str, object] | None], None],
) -> None:
    st_session({})

    out = ur.run_scraper_pipeline("https://a.com", _cfg(AgentMode.RULE_BASED))
    assert out == ([], 0)
