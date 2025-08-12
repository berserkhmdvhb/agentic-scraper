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
from typing import TYPE_CHECKING, Any

import httpx
import streamlit as st
from fastapi import status

from agentic_scraper import __api_version__ as api_version
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_SCRAPE_CONFIG_MERGED,
    MSG_ERROR_BACKEND_NO_JOB_ID,
    MSG_ERROR_CREATE_JOB,
    MSG_ERROR_EXTRACTION_FAILED,
    MSG_ERROR_FORBIDDEN_JOB_ACCESS,
    MSG_ERROR_NETWORK_HTTP,
    MSG_ERROR_USER_NOT_AUTHENTICATED,
    MSG_INFO_CREATING_JOB_SPINNER,
    MSG_INFO_JOB_NOT_CANCELABLE,
    MSG_INFO_NO_VALID_URLS,
    MSG_INFO_RUNNING_JOB_SPINNER,
    MSG_INFO_USING_CACHE,
    MSG_WARNING_JOB_NOT_FOUND,
)
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.frontend.ui_runner_helpers import (
    attach_openai_config,
    parse_job_result,
    render_invalid_url_section,
    render_job_error,
    render_valid_url_feedback,
    summarize_results,
    validate_and_deduplicate_urls,
)

if TYPE_CHECKING:
    from agentic_scraper.backend.scraper.schemas import ScrapedItem
    from agentic_scraper.frontend.models import PipelineConfig

logger = logging.getLogger(__name__)
settings = get_settings()


class BackendNoJobIdError(ValueError):
    """Raised when the backend response is missing the expected job id."""

    def __str__(self) -> str:  # ruff: TRY003-compliant
        return MSG_ERROR_BACKEND_NO_JOB_ID


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
    if not jwt:
        raise RuntimeError(MSG_ERROR_USER_NOT_AUTHENTICATED)
    return {"Authorization": f"Bearer {jwt}"}


async def create_scrape_job(urls: list[str], config: PipelineConfig) -> tuple[str, str | None]:
    """POST /scrapes/ to create a job. Returns (job_id, location_header)."""
    headers = await _auth_headers()

    # Build request body (only fields allowed by backend), stripping None values
    body: dict[str, Any] = {
        "urls": urls,
        "agent_mode": config.agent_mode,
        "fetch_concurrency": getattr(config, "fetch_concurrency", None),
        "llm_concurrency": getattr(config, "llm_concurrency", None),
        "screenshot_enabled": getattr(config, "screenshot_enabled", None),
        "verbose": getattr(config, "verbose", None),
        "retry_attempts": getattr(config, "retry_attempts", None),
        "llm_schema_retries": getattr(config, "llm_schema_retries", None),
    }
    body = {k: v for k, v in body.items() if v is not None}

    # Attach inline OpenAI creds ONLY if overriding stored ones (optional UX choice)
    agent_mode = getattr(config, "agent_mode", AgentMode.RULE_BASED)
    if isinstance(agent_mode, str):
        try:
            agent_mode = AgentMode(agent_mode)
        except ValueError:
            agent_mode = AgentMode.RULE_BASED

    if agent_mode != AgentMode.RULE_BASED and st.session_state.get("openai_credentials"):
        attach_openai_config(config, body)
    else:
        # Rule-based: make sure no LLM-only fields sneak in
        for k in ("llm_concurrency", "llm_schema_retries", "openai_model"):
            body.pop(k, None)
    logger.debug(
        MSG_DEBUG_SCRAPE_CONFIG_MERGED.format(config={k: body[k] for k in body if k != "urls"})
    )
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.post(
            f"{settings.backend_domain}/api/{api_version}/scrapes/",
            json=body,
            headers=headers,
            timeout=60,
        )

    # Expect 202 Accepted
    if resp.status_code != status.HTTP_202_ACCEPTED:
        msg = _safe_message(resp)
        raise httpx.HTTPStatusError(
            MSG_ERROR_CREATE_JOB.format(error=msg), request=resp.request, response=resp
        )

    data = resp.json() or {}
    job_id = data.get("id")
    if not job_id:
        raise BackendNoJobIdError
    return job_id, resp.headers.get("Location")


async def poll_scrape_job(job_id: str, *, interval_sec: float = 1.2) -> dict[str, Any]:
    """
    Poll the backend for a scrape job until it reaches a terminal state.

    Args:
        job_id (str): Backend job identifier.
        interval_sec (float): Delay between polls in seconds.

    Returns:
        dict[str, Any]: Final job payload. If not found or forbidden, returns a synthetic
        failed job with an 'error' message.
    """
    headers = await _auth_headers()

    async with httpx.AsyncClient(follow_redirects=True) as client:
        while True:
            resp = await client.get(
                f"{settings.backend_domain}/api/{api_version}/scrapes/{job_id}",
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

            if status_ in {"succeeded", "failed", "canceled"}:
                return job

            await asyncio.sleep(interval_sec)


async def cancel_scrape_job(job_id: str) -> bool:
    """DELETE /scrapes/{id}. Returns True if 204."""
    headers = await _auth_headers()

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.delete(
                f"{settings.backend_domain}/api/{api_version}/scrapes/{job_id}",
                headers=headers,
                timeout=60,
            )
    except (httpx.RequestError, httpx.HTTPStatusError):
        # Let the caller surface specific error text if needed; keep this small.
        return False

    if resp.status_code == status.HTTP_204_NO_CONTENT:
        return True
    if resp.status_code == status.HTTP_409_CONFLICT:
        st.info(MSG_INFO_JOB_NOT_CANCELABLE)
        return False

    # Surface unexpected errors
    st.error(_safe_message(resp))
    return False


# -------------------------
# Public entry point used by the UI
# -------------------------
def run_scraper_pipeline(raw_input: str, config: PipelineConfig) -> tuple[list[ScrapedItem], int]:
    """
    Validate URLs, create a scrape job, poll until completion, and render results.

    Returns:
        (items, skipped)
    """
    urls, invalid_lines = validate_and_deduplicate_urls(raw_input)
    render_invalid_url_section(invalid_lines)

    if not urls:
        st.warning(MSG_INFO_NO_VALID_URLS)
        return [], 0

    render_valid_url_feedback(urls)

    # Cache by URL list to avoid duplicate submissions in-session
    key = tuple(sorted(urls))
    if st.session_state.get("last_input_key") == key:
        st.info(MSG_INFO_USING_CACHE)
        return st.session_state.get("extracted_items", []), 0

    start = time.perf_counter()

    try:
        with st.spinner(MSG_INFO_CREATING_JOB_SPINNER):
            job_id, _ = asyncio.run(create_scrape_job(urls, config))

        # Simple live status indicator while polling
        with st.spinner(MSG_INFO_RUNNING_JOB_SPINNER):
            final_job = asyncio.run(poll_scrape_job(job_id))
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        st.error(MSG_ERROR_NETWORK_HTTP.format(error=e))
        return [], 0
    except (ValueError, RuntimeError) as e:
        # Specific, predictable failures (e.g., no JWT or malformed backend response)
        st.error(MSG_ERROR_EXTRACTION_FAILED.format(error=e))
        return [], 0
    else:
        status_ = (final_job.get("status") or "").lower()
        if status_ == "succeeded":
            items, skipped, _duration = parse_job_result(final_job)

            # Cache results
            st.session_state["extracted_items"] = items
            st.session_state["last_input_key"] = key

            summarize_results(items, skipped, start)
            return items, skipped

        # Failed or Canceled
        render_job_error(final_job)
        return [], 0
