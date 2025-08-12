"""
Low-level auth helpers for the Streamlit frontend.

This module centralizes:
- JWT extraction from URL/session
- Building Authorization headers
- Backend API base URL construction
- Fetching the user profile and OpenAI credentials

UI-specific rendering (login/logout buttons, toasts) stays in `ui_auth.py`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import httpx
import streamlit as st
from fastapi import status
from httpx import HTTPStatusError, RequestError

from agentic_scraper import __api_version__ as api_version
from agentic_scraper.backend.config.constants import EXPECTED_JWT_PARTS
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_JWT_FROM_URL,
    MSG_ERROR_USER_NOT_AUTHENTICATED,
    MSG_EXCEPTION_OPENAI_CREDENTIALS,
    MSG_EXCEPTION_OPENAI_CREDENTIALS_NETWORK,
    MSG_EXCEPTION_USER_PROFILE,
    MSG_EXCEPTION_USER_PROFILE_NETWORK,
    MSG_INFO_CREDENTIALS_SUCCESS,
    MSG_INFO_USER_PROFILE_SUCCESS,
    MSG_LOG_TOKEN_FROM_SESSION_STATE,
    MSG_WARNING_MALFORMED_JWT,
    MSG_WARNING_NO_JWT_FOUND,
)
from agentic_scraper.backend.config.types import OpenAIConfig
from agentic_scraper.backend.core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# --------- Basic utilities ---------


def ensure_https(domain: str) -> str:
    """Ensure the given domain starts with https:// for secure links."""
    if not domain:
        return ""
    if domain.startswith(("http://", "https://")):
        return domain
    return "https://" + domain


def api_base() -> str:
    """Return the backend API base URL using backend_domain (not the Auth0 audience)."""
    base = (settings.backend_domain or "").rstrip("/")
    if not base:
        return ""
    if not base.startswith("http"):
        base = "https://" + base
    return f"{base}/api/{api_version}"


def get_jwt_token_from_url_or_session() -> str | None:
    """
    Extract a JWT from ?token=... or session state.
    If found via URL, store it in session and clear query params.
    """
    token = st.query_params.get("token")

    if token:
        jwt_token = token[0] if isinstance(token, list) else token
        if isinstance(jwt_token, str) and len(jwt_token.split(".")) == EXPECTED_JWT_PARTS:
            st.session_state["jwt_token"] = jwt_token
            logger.debug(MSG_DEBUG_JWT_FROM_URL.format(token=jwt_token))
            st.query_params.clear()
            return jwt_token
        logger.warning(MSG_WARNING_MALFORMED_JWT.format(token=jwt_token))
        st.warning("⚠️ Token format appears invalid. Login may fail.")
        return None

    token_from_session = st.session_state.get("jwt_token")
    if isinstance(token_from_session, str):
        logger.debug(MSG_LOG_TOKEN_FROM_SESSION_STATE)
        return token_from_session

    logger.warning(MSG_WARNING_NO_JWT_FOUND)
    return None


def build_auth_headers() -> dict[str, str]:
    """Build Authorization headers from session JWT, or raise RuntimeError."""
    jwt = st.session_state.get("jwt_token")
    if not jwt:
        raise RuntimeError(MSG_ERROR_USER_NOT_AUTHENTICATED)
    return {"Authorization": f"Bearer {jwt}"}


# --------- Backend calls (sync) ---------


def fetch_user_profile(on_unauthorized: Callable[[], None] | None = None) -> None:
    """
    Fetch /user/me and stash in session_state['user_info'].
    If 401, optionally call `on_unauthorized()` (e.g., logout) and return.
    """
    try:
        headers = build_auth_headers()
    except RuntimeError:
        st.error("User is not authenticated!")
        return

    base = api_base()
    if not base:
        st.error("Backend domain is not configured.")
        return

    try:
        resp = httpx.get(f"{base}/user/me", headers=headers, timeout=20)
        if resp.status_code == status.HTTP_401_UNAUTHORIZED:
            st.warning("Session expired. Please log in again.")
            if on_unauthorized:
                on_unauthorized()
            return
        resp.raise_for_status()
    except HTTPStatusError as e:
        logger.exception(MSG_EXCEPTION_USER_PROFILE.format(error=e.response.text))
        st.error(f"Failed to fetch user profile: {e.response.text}")
        return
    except RequestError as e:
        logger.exception(MSG_EXCEPTION_USER_PROFILE_NETWORK)
        st.error(f"Network error while fetching user profile: {e}")
        return

    logger.info(MSG_INFO_USER_PROFILE_SUCCESS)
    st.session_state["user_info"] = resp.json()


def fetch_openai_credentials(on_unauthorized: Callable[[], None] | None = None) -> None:
    """
    Fetch /user/openai-credentials and stash a **masked preview** in
    session_state['openai_credentials_preview'] (do not overwrite real creds).
    If 401, optionally call `on_unauthorized()` (e.g., logout) and return.
    """
    try:
        headers = build_auth_headers()
    except RuntimeError:
        st.error("User is not authenticated!")
        return

    base = api_base()
    if not base:
        st.error("Backend domain is not configured.")
        return

    try:
        resp = httpx.get(f"{base}/user/openai-credentials", headers=headers, timeout=20)
        if resp.status_code == status.HTTP_401_UNAUTHORIZED:
            st.warning("Session expired. Please log in again.")
            if on_unauthorized:
                on_unauthorized()
            return
        resp.raise_for_status()
    except HTTPStatusError as e:
        logger.exception(MSG_EXCEPTION_OPENAI_CREDENTIALS.format(error=e.response.text))
        st.error(f"Failed to fetch OpenAI credentials: {e.response.text}")
        return
    except RequestError as e:
        logger.exception(MSG_EXCEPTION_OPENAI_CREDENTIALS_NETWORK)
        st.error(f"Network error while fetching OpenAI credentials: {e}")
        return

    data = resp.json() or {}
    openai_config = OpenAIConfig(
        api_key=data.get("api_key"),
        project_id=data.get("project_id"),
    )
    st.session_state["openai_credentials_preview"] = openai_config
    logger.info(MSG_INFO_CREDENTIALS_SUCCESS)
