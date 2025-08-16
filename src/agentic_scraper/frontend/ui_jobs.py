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
import time as _time
from collections.abc import Iterable
from typing import Any

import httpx
import streamlit as st
from fastapi import status
from streamlit_autorefresh import st_autorefresh

from agentic_scraper.backend.config.constants import SESSION_KEYS
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
from agentic_scraper.frontend.ui_display import display_results
from agentic_scraper.frontend.ui_runner_helpers import (
    parse_job_result,
    render_job_error,
    summarize_results,
)

settings = get_settings()
_AUTO_REFRESH_SECONDS = 2


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
        # Handle auth errors explicitly BEFORE raise_for_status
        if resp.status_code == status.HTTP_401_UNAUTHORIZED:
            if "jwt_token" in st.session_state:
                del st.session_state["jwt_token"]
            st.info(MSG_INFO_LOGIN_TO_VIEW_JOBS)
            return [], None
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
    """Fetch a single job by id. Returns the job dict or None on error/not-found."""
    payload: dict[str, Any] | None = None

    base = api_base()
    if not base:
        st.error(MSG_ERROR_BACKEND_DOMAIN_NOT_CONFIGURED)
        return None  # If you want literally one return, see alternative below.

    try:
        resp = _get(f"{base}/scrapes/{job_id}")
        code = resp.status_code

        if code == status.HTTP_404_NOT_FOUND:
            st.warning(MSG_WARNING_JOB_NOT_FOUND)
        elif code == status.HTTP_403_FORBIDDEN:
            st.error(MSG_ERROR_FORBIDDEN_JOB_ACCESS)
        elif code == status.HTTP_401_UNAUTHORIZED:
            if "jwt_token" in st.session_state:
                del st.session_state["jwt_token"]
            st.info(MSG_INFO_LOGIN_TO_VIEW_JOBS)
        else:
            # Will raise for 4xx/5xx not handled above
            resp.raise_for_status()
            data = resp.json() or {}
            payload = data if isinstance(data, dict) else {}
    except httpx.HTTPStatusError as e:
        st.error(MSG_ERROR_FETCH_JOB.format(error=e.response.text))
    except httpx.RequestError as e:
        st.error(MSG_ERROR_FETCH_JOB_NETWORK.format(error=e))

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


def _job_package_download_button(job: dict[str, Any]) -> None:
    """Download the full job payload (metadata + stats + raw results)."""
    if (job.get("status") or "").lower() != "succeeded":
        return
    try:
        # Export the entire backend payload for this job
        payload_str = json.dumps(job, indent=2)
    except (TypeError, ValueError):
        return
    # Put the button in a right-aligned column so it doesn't look like a wide primary CTA
    _, right = st.columns([3, 1])
    with right:
        st.download_button(
            "⬇️ Download job package (JSON)",
            data=payload_str,
            file_name=f"scrape_{job.get('id', 'job')}.job.json",
            mime="application/json",
            help="Full payload including job metadata, stats, and raw results.",
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
    if (job.get("status") or "").lower() in {"queued", "running"} and 0.0 <= progress <= 1.0:
        st.progress(progress, text=f"Progress: {int(progress * 100)}%")

    status_lower = (job.get("status") or "").lower()

    if status_lower == "succeeded":
        # Split success view into tabs to reduce vertical sprawl
        tab_overview, tab_results = st.tabs(["Overview", "Results"])

        with tab_overview:
            items, skipped, duration = parse_job_result(job)
            fake_start = _time.perf_counter() - float(duration or 0.0)
            summarize_results(items, skipped, fake_start)
            # Smaller, scoped download: the full job payload
            _job_package_download_button(job)
            st.caption(
                "Includes job metadata, stats, and raw results. "
                "For table-only exports, see the Results tab."
            )

            # Optional quick peek at extracted URLs (collapsed by default)
            if items:
                with st.expander("🔗 Quick view: URLs only", expanded=False):
                    for it in items:
                        url = it.get("url") if isinstance(it, dict) else getattr(it, "url", None)
                        if url:
                            st.write(f"- [{url}]({url})")

        with tab_results:
            screenshot_enabled = bool(
                st.session_state.get(SESSION_KEYS["screenshot_enabled"], False)
            )
            # Pass job_id so the table export filenames can include it
            display_results(
                items, job_id=str(job.get("id", "")), screenshot_enabled=screenshot_enabled
            )

    elif status_lower in {"failed", "canceled"}:
        render_job_error(job)

    # Cancel button for queued/running
    if status_lower in {"queued", "running"} and st.button(
        "🛑 Cancel Job", use_container_width=True
    ):
        job_id = job.get("id")
        if isinstance(job_id, str) and cancel_job(job_id):
            st.rerun()


# -------------------------
# Public entry point: Jobs Tab
# -------------------------


def _is_active(job: dict[str, Any]) -> bool:
    """
    Return True if a job is in an active state (queued or running).
    """
    status_lower = str(job.get("status") or "").lower()
    return status_lower in {"queued", "running"}


def _init_and_get_cursor(cursor_key: str = "jobs_cursor_stack") -> str | None:
    if cursor_key not in st.session_state:
        st.session_state[cursor_key] = []  # stack of cursors (for back navigation)
    return st.session_state[cursor_key][-1] if st.session_state[cursor_key] else None


def _count_active(items: list[dict[str, Any]]) -> int:
    return sum((str(j.get("status") or "").lower() in {"queued", "running"}) for j in items)


def _render_jobs_table(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = _build_rows(items)
    st.dataframe(rows, use_container_width=True, hide_index=True)
    job_ids: list[str] = [str(r["id"]) for r in rows if r.get("id") is not None]
    return rows, job_ids


def _select_job(job_ids: list[str], preselect_job_id: str | None) -> str | None:
    if not job_ids:
        return None
    default_index = job_ids.index(preselect_job_id) if preselect_job_id in job_ids else 0
    return st.selectbox("Select a job", options=job_ids, index=default_index)


def _maybe_list_autorefresh(items: list[dict[str, Any]], *, enabled: bool) -> None:
    if enabled and any(_is_active(j) for j in items):
        st_autorefresh(interval=_AUTO_REFRESH_SECONDS * 1000, key="jobs_list_auto_refresh")


def _handle_selected_job(
    selected_id: str | None,
    *,
    auto_refresh: bool,
    manual_refresh_clicked: bool,
) -> None:
    if not selected_id:
        return
    job: dict[str, Any] | None = fetch_job(selected_id)
    if job:
        _render_job_detail(job)

    if auto_refresh and not manual_refresh_clicked:
        if job and _is_active(job):
            st.caption(f"🔄 Auto-refreshing every {_AUTO_REFRESH_SECONDS} seconds…")
            st_autorefresh(interval=_AUTO_REFRESH_SECONDS * 1000, key="jobs_auto_refresh")
        else:
            _time.sleep(_AUTO_REFRESH_SECONDS)
            st.rerun()


def render_jobs_tab(preselect_job_id: str | None = None) -> None:
    """Render the Jobs tab UI."""
    st.header("🧭 Jobs")

    if "jwt_token" not in st.session_state:
        st.info(MSG_INFO_LOGIN_TO_VIEW_JOBS)
        return

    status_filter, limit, auto_refresh, refresh_clicked = _render_filters()

    cursor = _init_and_get_cursor()
    items, next_cursor = fetch_jobs(status_filter, limit, cursor)

    _maybe_list_autorefresh(items, enabled=auto_refresh)
    _render_pagination_toolbar("jobs_cursor_stack", cursor, next_cursor)

    if not items:
        st.info(MSG_INFO_NO_JOBS_FOUND)
        return

    active_count = _count_active(items)
    if active_count:
        st.caption(f"🟦 Active jobs: {active_count}")

    _, job_ids = _render_jobs_table(items)
    selected_id = _select_job(job_ids, preselect_job_id)

    _handle_selected_job(
        selected_id, auto_refresh=auto_refresh, manual_refresh_clicked=refresh_clicked
    )
