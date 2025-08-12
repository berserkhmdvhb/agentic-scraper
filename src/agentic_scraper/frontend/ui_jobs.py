"""
Jobs tab for listing, inspecting, and cancelling scrape jobs.

Endpoints used:
- GET   /scrapes?status_=&limit=&cursor=
- GET   /scrapes/{job_id}
- DELETE /scrapes/{job_id}

Prereqs:
- User must be authenticated; JWT expected in st.session_state['jwt_token']
- Backend domain configured in settings.backend_domain
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

import httpx
import streamlit as st
from fastapi import status

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_BACKEND_DOMAIN_NOT_CONFIGURED,
    MSG_ERROR_CANCEL_JOB,
    MSG_ERROR_CANCEL_JOB_NETWORK,
    MSG_ERROR_FETCH_JOB,
    MSG_ERROR_FETCH_JOB_NETWORK,
    MSG_ERROR_FORBIDDEN_JOB_ACCESS,
    MSG_ERROR_LIST_JOBS,
    MSG_ERROR_LIST_JOBS_NETWORK,
    MSG_INFO_JOB_NOT_CANCELABLE,
    MSG_INFO_LOGIN_TO_VIEW_JOBS,
    MSG_INFO_NO_JOBS_FOUND,
    MSG_SUCCESS_JOB_CANCELED,
    MSG_WARNING_JOB_NOT_FOUND,
)
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.frontend.ui_auth_helpers import api_base, build_auth_headers

settings = get_settings()


# -------------------------
# HTTP helpers
# -------------------------


def _get(url: str, *, timeout: int = 30) -> httpx.Response:
    headers = build_auth_headers()
    with httpx.Client() as client:
        return client.get(url, headers=headers, timeout=timeout)


def _delete(url: str, *, timeout: int = 30) -> httpx.Response:
    headers = build_auth_headers()
    with httpx.Client() as client:
        return client.delete(url, headers=headers, timeout=timeout)


def _safe_message(resp: httpx.Response) -> str:
    """Extract best-effort message from a response."""
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

def fetch_jobs(
    status_filter: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Fetch jobs from the backend.

    Returns:
        (items, next_cursor)
        - items: list of job dicts
        - next_cursor: pagination cursor or None

    Notes:
        - `status_filter` can be one of: queued/running/succeeded/failed/canceled or None/"All".
        - Always call the trailing-slash endpoint to avoid redirects.
    """
    base = api_base()
    if not base:
        st.error(MSG_ERROR_BACKEND_DOMAIN_NOT_CONFIGURED)
        return [], None

    # Build query params safely (let httpx encode them)
    params: dict[str, str] = {}
    if status_filter and status_filter.lower() != "all":
        params["status_"] = status_filter.lower()
    params["limit"] = str(limit)
    if cursor:
        params["cursor"] = cursor

    url = f"{base}/scrapes/"
    if params:
        query_str = str(httpx.QueryParams(params))  # e.g., "status_=running&limit=20"
        url = f"{url}?{query_str}"

    try:
        resp = _get(url)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        st.error(MSG_ERROR_LIST_JOBS.format(error=e.response.text))
        return [], None
    except httpx.RequestError as e:
        st.error(MSG_ERROR_LIST_JOBS_NETWORK.format(error=e))
        return [], None

    payload: dict[str, Any] = resp.json() or {}
    if not isinstance(payload, dict):
        payload = {}

    raw_items: Any = payload.get("items", [])
    items: list[dict[str, Any]] = [it for it in raw_items if isinstance(it, dict)]

    next_cursor_val: Any = payload.get("next_cursor")
    next_cursor: str | None = next_cursor_val if isinstance(next_cursor_val, str) else None

    return items, next_cursor


def fetch_job(job_id: str) -> dict[str, Any] | None:
    base = api_base()
    if not base:
        st.error(MSG_ERROR_BACKEND_DOMAIN_NOT_CONFIGURED)
        return None

    try:
        resp = _get(f"{base}/scrapes/{job_id}")
        if resp.status_code == status.HTTP_404_NOT_FOUND:
            st.warning(MSG_WARNING_JOB_NOT_FOUND)
            return None
        if resp.status_code == status.HTTP_403_FORBIDDEN:
            st.error(MSG_ERROR_FORBIDDEN_JOB_ACCESS)
            return None
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        st.error(MSG_ERROR_FETCH_JOB.format(error=e.response.text))
        return None
    except httpx.RequestError as e:
        st.error(MSG_ERROR_FETCH_JOB_NETWORK.format(error=e))
        return None

    payload: dict[str, Any] = resp.json() or {}
    return payload


def cancel_job(job_id: str) -> bool:
    base = api_base()
    if not base:
        st.error(MSG_ERROR_BACKEND_DOMAIN_NOT_CONFIGURED)
        return False

    try:
        resp = _delete(f"{base}/scrapes/{job_id}")
        code = resp.status_code

        success = False
        if code == status.HTTP_204_NO_CONTENT:
            st.success(MSG_SUCCESS_JOB_CANCELED)
            success = True
        elif code == status.HTTP_409_CONFLICT:
            st.info(MSG_INFO_JOB_NOT_CANCELABLE)
        elif code == status.HTTP_404_NOT_FOUND:
            st.warning(MSG_WARNING_JOB_NOT_FOUND)
        elif code == status.HTTP_403_FORBIDDEN:
            st.error(MSG_ERROR_FORBIDDEN_JOB_ACCESS)
        else:
            # Unexpected status → show server message
            st.error(MSG_ERROR_CANCEL_JOB.format(error=_safe_message(resp)))
    except httpx.HTTPStatusError as e:
        st.error(MSG_ERROR_CANCEL_JOB.format(error=e.response.text))
        success = False
    except httpx.RequestError as e:
        st.error(MSG_ERROR_CANCEL_JOB_NETWORK.format(error=e))
        success = False
    else:
        return success

    return False


# -------------------------
# UI helpers
# -------------------------


def _status_badge(status_: str) -> str:
    s = (status_ or "").upper()
    color = {
        "QUEUED": "gray",
        "RUNNING": "blue",
        "SUCCEEDED": "green",
        "FAILED": "red",
        "CANCELED": "orange",
    }.get(s, "gray")
    return (
        f"<span style='"
        f"background:{color};"
        f"color:white;"
        f"padding:2px 6px;"
        f"border-radius:6px;"
        f"font-size:0.8rem'"
        f">{s}</span>"
    )


def _result_download_button(job: dict[str, Any]) -> None:
    if (job.get("status") or "").lower() != "succeeded":
        return
    result = job.get("result") or {}
    try:
        json_str = json.dumps(result, indent=2)
    except (TypeError, ValueError):
        return
    st.download_button(
        "⬇️ Download result JSON",
        data=json_str,
        file_name=f"scrape_{job.get('id', 'job')}.json",
        mime="application/json",
        use_container_width=True,
    )


def _build_rows(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": j.get("id"),
            "status": j.get("status"),
            "progress": j.get("progress", 0.0),
            "created_at": j.get("created_at"),
            "updated_at": j.get("updated_at"),
        }
        for j in items
    ]


def _render_filters() -> tuple[str, int, bool, bool]:
    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
    with col1:
        status_filter = st.selectbox(
            "Status",
            options=["All", "queued", "running", "succeeded", "failed", "canceled"],
            index=0,
        )
    with col2:
        limit = st.slider("Limit", 5, 50, 20)
    with col3:
        auto_refresh = st.toggle("Auto-refresh", value=False, help="Refresh every few seconds")
    with col4:
        refresh = st.button("🔄 Refresh")
    return status_filter, limit, auto_refresh, refresh


def _render_pagination_toolbar(
    cursor_stack_key: str, cursor: str | None, next_cursor: str | None
) -> None:
    tcol1, tcol2, tcol3 = st.columns(3)
    with tcol1:
        if st.button("⬅️ Prev") and st.session_state[cursor_stack_key]:
            st.session_state[cursor_stack_key].pop()
            st.rerun()
    with tcol2:
        st.write(f"Page cursor: `{cursor or '—'}`")
    with tcol3:
        if next_cursor and st.button("Next ➡️"):
            st.session_state[cursor_stack_key].append(next_cursor)
            st.rerun()


def _render_job_detail(job: dict[str, Any]) -> None:
    st.markdown(f"**Job ID:** `{job.get('id')}`")
    st.markdown(f"Status: {_status_badge(job.get('status', ''))}", unsafe_allow_html=True)

    progress = float(job.get("progress", 0.0) or 0.0)
    if 0.0 <= progress <= 1.0:
        st.progress(progress, text=f"Progress: {int(progress * 100)}%")

    if (job.get("status") or "").lower() == "succeeded":
        stats = (job.get("result") or {}).get("stats") or {}
        st.metric("✅ Success", stats.get("num_success", 0))
        st.metric("⚠️ Failed", stats.get("num_failed", 0))
        st.metric("⏱️ Duration (s)", stats.get("duration_sec", 0.0))
        _result_download_button(job)

    # Cancel button for queued/running
    if (str(job.get("status") or "")).lower() in {"queued", "running"} and st.button(
        "🛑 Cancel Job", use_container_width=True
    ):
        job_id = job.get("id")
        if isinstance(job_id, str) and cancel_job(job_id):
            st.rerun()


# -------------------------
# Public entry point: Jobs Tab
# -------------------------


def render_jobs_tab() -> None:
    """Render the Jobs tab UI."""
    st.header("🧭 Jobs")

    if "jwt_token" not in st.session_state:
        st.info(MSG_INFO_LOGIN_TO_VIEW_JOBS)
        return

    status_filter, limit, auto_refresh, refresh = _render_filters()

    # Pagination state
    cursor_key = "jobs_cursor_stack"
    if cursor_key not in st.session_state:
        st.session_state[cursor_key] = []  # stack of cursors (for back navigation)

    cursor = st.session_state[cursor_key][-1] if st.session_state[cursor_key] else None

    # Fetch list
    items, next_cursor = fetch_jobs(status_filter, limit, cursor)

    # Toolbar for pagination
    _render_pagination_toolbar(cursor_key, cursor, next_cursor)

    # Jobs table
    if not items:
        st.info(MSG_INFO_NO_JOBS_FOUND)
        return

    rows = _build_rows(items)
    st.dataframe(rows, use_container_width=True, hide_index=True)

    # Selection & actions
    job_ids = [r["id"] for r in rows if r.get("id")]
    selected_id = None
    if job_ids:
        selected_id = st.selectbox("Select a job", options=job_ids, index=0 if job_ids else None)
    if selected_id:
        job = fetch_job(selected_id)
        if job:
            _render_job_detail(job)

    # Auto-refresh logic
    if auto_refresh and not refresh:
        st.rerun()
