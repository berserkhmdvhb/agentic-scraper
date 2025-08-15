"""
UI runner for triggering and monitoring scraping via the backend REST API (job-based).

Changes in this version:
- Create jobs via POST /scrapes/ (202 + Location header)
- Poll job status via GET /scrapes/{id} until terminal state
- Optional cancel via DELETE /scrapes/{id}
- Removed legacy synchronous /scrape/start flow and local pipeline hooks
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import httpx
import streamlit as st
from fastapi import status

from agentic_scraper.backend.config.constants import REQUIRED_CONFIG_FIELDS_FOR_LLM
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_JOB_ID_FROM_BODY,
    MSG_DEBUG_LLM_FIELDS_ATTACHED,
    MSG_DEBUG_POLL_START,
    MSG_DEBUG_POLL_STATUS_CHANGE,
    MSG_DEBUG_REQUEST_PAYLOAD_KEYS,
    MSG_DEBUG_REQUEST_TARGET,
    MSG_DEBUG_RESPONSE_BODY_COMPACT,
    MSG_DEBUG_RESPONSE_META,
    MSG_DEBUG_SCRAPE_CONFIG_MERGED,
    MSG_ERROR_BACKEND_NO_JOB_ID,
    MSG_ERROR_CREATE_JOB,
    MSG_ERROR_EXTRACTION_FAILED,
    MSG_ERROR_FORBIDDEN_JOB_ACCESS,
    MSG_ERROR_HTTP_COMPACT,
    MSG_ERROR_INVALID_AGENT_MODE,
    MSG_ERROR_MISSING_JWT,
    MSG_ERROR_MISSING_LLM_FIELDS,
    MSG_ERROR_MISSING_OPENAI_CREDENTIALS,
    MSG_ERROR_NETWORK_HTTP,
    MSG_ERROR_POLLING_TIMEOUT,
    MSG_ERROR_USER_NOT_AUTHENTICATED,
    MSG_INFO_CREATING_JOB_SPINNER,
    MSG_INFO_JOB_NOT_CANCELABLE,
    MSG_INFO_LOGIN_TO_VIEW_JOBS,
    MSG_INFO_NO_VALID_URLS,
    MSG_WARNING_JOB_NOT_FOUND,
    MSG_WARNING_LLM_FIELDS_MISSING,
    MSG_WARNING_POLL_TIMEOUT,
)
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.frontend.ui_auth_helpers import api_base
from agentic_scraper.frontend.ui_runner_helpers import (
    attach_openai_config,
    render_invalid_url_section,
    render_valid_url_feedback,
    validate_and_deduplicate_urls,
)

if TYPE_CHECKING:
    from agentic_scraper.frontend.models import PipelineConfig

logger = logging.getLogger(__name__)
settings = get_settings()

_LOG_TRUNCATE = 500


def _truncate(s: str, n: int = _LOG_TRUNCATE) -> str:
    if not isinstance(s, str):
        return str(s)
    return s if len(s) <= n else s[:n] + "...(truncated)"


class BackendNoJobIdError(ValueError):
    """Raised when the backend response is missing the expected job id."""

    def __str__(self) -> str:  # ruff: TRY003-compliant
        return MSG_ERROR_BACKEND_NO_JOB_ID


# -------------------------
# Internal helpers
# -------------------------
def _request_base_url() -> str:
    return api_base()


def _build_request_body(urls: list[str], config: PipelineConfig) -> dict[str, Any]:
    """Collect allowed fields and strip None values."""
    body: dict[str, Any] = {
        "urls": urls,
        "agent_mode": getattr(config, "agent_mode", None),
        "fetch_concurrency": getattr(config, "fetch_concurrency", None),
        "llm_concurrency": getattr(config, "llm_concurrency", None),
        "screenshot_enabled": getattr(config, "screenshot_enabled", None),
        "verbose": getattr(config, "verbose", None),
        "retry_attempts": getattr(config, "retry_attempts", None),
        "llm_schema_retries": getattr(config, "llm_schema_retries", None),
    }
    return {k: v for k, v in body.items() if v is not None}


def _normalize_agent_mode(mode_val: AgentMode | str | None) -> AgentMode:
    """Coerce agent_mode (string/enum) to AgentMode, raising with message constant on error."""
    if isinstance(mode_val, AgentMode):
        return mode_val
    if isinstance(mode_val, str):
        try:
            return AgentMode(mode_val)
        except ValueError as err:
            raise RuntimeError(MSG_ERROR_INVALID_AGENT_MODE.format(mode=mode_val)) from err
    return AgentMode.RULE_BASED


def _prepare_llm_fields(
    agent_mode: AgentMode, config: PipelineConfig, body: dict[str, Any]
) -> None:
    """
    Rule-based: ensure LLM-only fields are stripped.
    LLM modes : attach OpenAI config and validate required fields.
    """
    if agent_mode == AgentMode.RULE_BASED:
        for k in REQUIRED_CONFIG_FIELDS_FOR_LLM:
            body.pop(k, None)
        return

    # LLM modes
    if not attach_openai_config(config, body):
        raise RuntimeError(MSG_ERROR_MISSING_OPENAI_CREDENTIALS)

    # Inline creds are optional when stored on backend; don't require them here.
    must_have = [k for k in REQUIRED_CONFIG_FIELDS_FOR_LLM if k != "openai_credentials"]
    missing = [k for k in must_have if k not in body]
    if missing:
        raise RuntimeError(MSG_ERROR_MISSING_LLM_FIELDS.format(fields=", ".join(missing)))

    with suppress(Exception):
        present = [k for k in REQUIRED_CONFIG_FIELDS_FOR_LLM if k in body]
        if present:
            logger.debug(MSG_DEBUG_LLM_FIELDS_ATTACHED.format(fields=present))
        if missing:
            logger.warning(MSG_WARNING_LLM_FIELDS_MISSING.format(fields=missing))


# -------------------------
# REST helpers (async)
# -------------------------
def _safe_message(resp: httpx.Response) -> str:
    """
    Best-effort extraction of a human-readable error message from an HTTP response.

    Tries JSON first:
      - If JSON is a string, return it.
      - If JSON is an object/array, return a compact JSON string.
    Falls back to response text if JSON parsing fails or yields an unsupported type.
    """
    try:
        data = resp.json()
    except ValueError:
        return resp.text

    if isinstance(data, str):
        return data
    if data is None:
        return resp.text

    try:
        return json.dumps(data)
    except (TypeError, ValueError):
        return resp.text


async def _auth_headers() -> dict[str, str]:
    jwt = st.session_state.get("jwt_token")
    if not isinstance(jwt, str) or not jwt.strip():
        logger.error(MSG_ERROR_MISSING_JWT)
        raise RuntimeError(MSG_ERROR_USER_NOT_AUTHENTICATED)
    return {"Authorization": f"Bearer {jwt}"}


async def create_scrape_job(
    urls: list[str],
    config: PipelineConfig,
) -> tuple[str, str | None]:
    """POST /scrapes/ to create a job. Returns (job_id, location_header)."""
    headers = await _auth_headers()

    # Build request body
    body = _build_request_body(urls, config)

    # Log payload shape & agent_mode type
    mode_val = getattr(config, "agent_mode", None)
    with suppress(Exception):
        logger.debug(
            MSG_DEBUG_REQUEST_PAYLOAD_KEYS.format(
                keys=sorted(body.keys()), mode=mode_val, type=type(mode_val).__name__
            )
        )

    # Attach inline OpenAI creds or strip LLM-only fields based on mode
    agent_mode = _normalize_agent_mode(mode_val)
    _prepare_llm_fields(agent_mode, config, body)

    logger.debug(
        MSG_DEBUG_SCRAPE_CONFIG_MERGED.format(config={k: body[k] for k in body if k != "urls"})
    )
    base = _request_base_url()
    url = f"{base}/scrapes/"
    logger.debug(MSG_DEBUG_REQUEST_TARGET.format(method="POST", url=url))
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.post(
            url,
            json=body,
            headers=headers,
            timeout=60,
        )

    # Expect 202 Accepted
    if resp.status_code != status.HTTP_202_ACCEPTED:
        msg = _truncate(_safe_message(resp))
        logger.error(MSG_ERROR_HTTP_COMPACT.format(method="POST", url=url, error=msg))
        raise httpx.HTTPStatusError(
            MSG_ERROR_CREATE_JOB.format(error=msg), request=resp.request, response=resp
        )

    logger.debug(
        MSG_DEBUG_RESPONSE_META.format(
            status=resp.status_code, location=resp.headers.get("Location")
        )
    )
    with suppress(Exception):
        logger.debug(MSG_DEBUG_RESPONSE_BODY_COMPACT.format(body=_truncate(resp.text)))

    data = resp.json() or {}
    job_id = data.get("id")
    if not job_id:
        logger.error(MSG_ERROR_BACKEND_NO_JOB_ID)
        raise BackendNoJobIdError
    logger.debug(MSG_DEBUG_JOB_ID_FROM_BODY.format(job_id=job_id))
    return job_id, resp.headers.get("Location")


async def poll_scrape_job(
    job_id: str, *, interval_sec: float = 1.2, max_seconds: float = 300.0
) -> dict[str, Any]:
    headers = await _auth_headers()
    deadline = time.perf_counter() + max_seconds
    logger.debug(
        MSG_DEBUG_POLL_START.format(job_id=job_id, interval=interval_sec, timeout=max_seconds)
    )
    async with httpx.AsyncClient(follow_redirects=True) as client:
        while True:
            base = _request_base_url()
            url = f"{base}/scrapes/{job_id}"
            resp = await client.get(
                url,
                headers=headers,
                timeout=60,
            )

            if resp.status_code == status.HTTP_404_NOT_FOUND:
                return {"status": "failed", "error": MSG_WARNING_JOB_NOT_FOUND}
            if resp.status_code == status.HTTP_403_FORBIDDEN:
                return {"status": "failed", "error": MSG_ERROR_FORBIDDEN_JOB_ACCESS}

            resp.raise_for_status()
            job: dict[str, Any] = resp.json()
            status_ = str(job.get("status") or "").lower()

            with suppress(Exception):
                progress = job.get("progress")
                result = job.get("result") or {}
                items_count = len(result.get("items") or []) if isinstance(result, dict) else 0
                logger.debug(
                    MSG_DEBUG_POLL_STATUS_CHANGE.format(
                        job_id=job_id, status=status_, progress=progress, items=items_count
                    )
                )

            if status_ in {"succeeded", "failed", "canceled"}:
                return job

            if time.perf_counter() >= deadline:
                logger.warning(MSG_WARNING_POLL_TIMEOUT.format(job_id=job_id, elapsed=max_seconds))
                return {"status": "failed", "error": MSG_ERROR_POLLING_TIMEOUT}

            await asyncio.sleep(interval_sec)


async def cancel_scrape_job(job_id: str) -> bool:
    """DELETE /scrapes/{id}. Returns True if 204."""
    headers = await _auth_headers()

    try:
        base = _request_base_url()
        url = f"{base}/scrapes/{job_id}"
        logger.debug(MSG_DEBUG_REQUEST_TARGET.format(method="DELETE", url=url))
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.delete(
                url,
                headers=headers,
                timeout=60,
            )
    except (httpx.RequestError, httpx.HTTPStatusError):
        return False

    if resp.status_code == status.HTTP_204_NO_CONTENT:
        return True
    if resp.status_code == status.HTTP_409_CONFLICT:
        st.info(MSG_INFO_JOB_NOT_CANCELABLE)
        return False

    msg = _truncate(_safe_message(resp))
    logger.error(MSG_ERROR_HTTP_COMPACT.format(method="DELETE", url=url, error=msg))
    st.error(msg)
    return False


# -------------------------
# Public entry point used by the UI
# -------------------------


# New: simple submit helper that only creates a job and returns its id
def submit_scrape_job(raw_input: str, config: PipelineConfig) -> str | None:
    urls, invalid_lines = validate_and_deduplicate_urls(raw_input)
    render_invalid_url_section(invalid_lines)

    if not urls:
        st.warning(MSG_INFO_NO_VALID_URLS)
        return None

    render_valid_url_feedback(urls)

    try:
        with st.spinner(MSG_INFO_CREATING_JOB_SPINNER):
            job_id, _ = asyncio.run(create_scrape_job(urls, config))
    except httpx.HTTPStatusError as e:
        resp = e.response
        code = getattr(resp, "status_code", None)
        # Mirror the friendly handling you use in ui_jobs.py
        if code == status.HTTP_401_UNAUTHORIZED:
            if "jwt_token" in st.session_state:
                del st.session_state["jwt_token"]
            st.info(MSG_INFO_LOGIN_TO_VIEW_JOBS)
        elif code == status.HTTP_403_FORBIDDEN:
            st.error(MSG_ERROR_FORBIDDEN_JOB_ACCESS)
        else:
            st.error(MSG_ERROR_CREATE_JOB.format(error=resp.text if resp is not None else e))
        return None
    except httpx.RequestError as e:
        st.error(MSG_ERROR_NETWORK_HTTP.format(error=e))
        return None
    except (ValueError, RuntimeError) as e:
        st.error(MSG_ERROR_EXTRACTION_FAILED.format(error=e))
        return None

    if job_id:
        st.session_state["last_job_id"] = job_id
        st.success("✅ Job started — monitor progress or cancel in the **Jobs** tab.")
        return job_id
    return None


# Replace the existing definition entirely
def run_scraper_pipeline(
    raw_input: str, config: PipelineConfig
) -> tuple[list[dict[str, Any]], int]:
    """
    Non-blocking: only submit a job and return immediately.
    The Jobs tab is responsible for monitoring and displaying results.
    """
    submit_scrape_job(raw_input, config)
    # We no longer return extracted items here; results are shown in Jobs.
    return [], 0
