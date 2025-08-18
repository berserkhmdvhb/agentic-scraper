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
import urllib.parse
from collections.abc import Callable

import httpx
import streamlit as st
from fastapi import status

from agentic_scraper import __api_version__ as api_version
from agentic_scraper.backend.config.constants import (
    AUTH0_LOGOUT_PATH,
    EXPECTED_JWT_PARTS,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_JWT_FROM_URL,
    MSG_ERROR_USER_NOT_AUTHENTICATED,
    MSG_EXCEPTION_OPENAI_CREDENTIALS,
    MSG_EXCEPTION_OPENAI_CREDENTIALS_NETWORK,
    MSG_EXCEPTION_USER_PROFILE,
    MSG_EXCEPTION_USER_PROFILE_NETWORK,
    MSG_INFO_AUTH0_FORCE_LOGIN_URI,
    MSG_INFO_AUTH0_LOGIN_URI,
    MSG_INFO_AUTH0_LOGOUT_URI,
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
    Extract a JWT from the URL query (?token=...) or from Streamlit session state.

    If a token is found in the URL, this function:
      - Validates the basic JWT shape (header.payload.signature)
      - Saves it to `st.session_state["jwt_token"]`
      - Sets `st.session_state["auth_pending"] = True` so the UI can hide the login button
      - Clears the query params to avoid re-processing on rerun

    If no token is found in the URL, it falls back to `st.session_state["jwt_token"]`.

    Returns:
        str | None: The JWT string if found and well-formed; otherwise None.
    """
    token = st.query_params.get("token")

    if token:
        jwt_token = token[0] if isinstance(token, list) else token
        if isinstance(jwt_token, str):
            jwt_token = jwt_token.strip()

        if isinstance(jwt_token, str) and len(jwt_token.split(".")) == EXPECTED_JWT_PARTS:
            st.session_state["auth_pending"] = True
            st.session_state["jwt_token"] = jwt_token
            # Log a masked preview to avoid leaking the full token
            preview = f"{jwt_token[:10]}…"
            logger.debug(MSG_DEBUG_JWT_FROM_URL.format(token=preview))
            st.query_params.clear()
            return jwt_token

        # Malformed token in URL
        logger.warning(MSG_WARNING_MALFORMED_JWT.format(token=jwt_token))
        st.query_params.clear()
        st.warning("⚠️ Token format appears invalid. Login may fail.")
        return None

    # Fallback - already in session
    token_from_session = st.session_state.get("jwt_token")
    if isinstance(token_from_session, str):
        logger.debug(MSG_LOG_TOKEN_FROM_SESSION_STATE)
        st.session_state.pop("auth_pending", None)
        return token_from_session

    # No token anywhere
    logger.warning(MSG_WARNING_NO_JWT_FOUND)
    st.session_state.pop("auth_pending", None)
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
    except httpx.HTTPStatusError as e:
        logger.exception(MSG_EXCEPTION_USER_PROFILE.format(error=e.response.text))
        st.error(f"Failed to fetch user profile: {e.response.text}")
        return
    except httpx.RequestError as e:
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
    except httpx.HTTPStatusError as e:
        logger.exception(MSG_EXCEPTION_OPENAI_CREDENTIALS.format(error=e.response.text))
        st.error(f"Failed to fetch OpenAI credentials: {e.response.text}")
        return
    except httpx.RequestError as e:
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


def fetch_openai_credentials_status(
    on_unauthorized: Callable[[], None] | None = None,
) -> dict[str, bool] | None:
    """
    Fetch /user/openai-credentials/status and return {"has_credentials": bool}.
    Does not modify UI directly; callers can set st.session_state flags as needed.
    If 401, optionally call `on_unauthorized()` (e.g., logout) and return None.
    """
    # Build headers or fail fast
    try:
        headers = build_auth_headers()
    except RuntimeError:
        st.error("User is not authenticated!")
        return None

    # Resolve API base or fail fast
    base = api_base()
    if not base:
        st.error("Backend domain is not configured.")
        return None

    result: dict[str, bool] | None

    try:
        resp = httpx.get(f"{base}/user/openai-credentials/status", headers=headers, timeout=15)
        if resp.status_code == status.HTTP_401_UNAUTHORIZED:
            st.warning("Session expired. Please log in again.")
            if on_unauthorized:
                on_unauthorized()
            result = None
        else:
            resp.raise_for_status()
            # Parse JSON payload safely
            try:
                data = resp.json()
            except ValueError:
                # JSON decoding error; treat as "no credentials"
                logger.exception(MSG_EXCEPTION_OPENAI_CREDENTIALS)
                result = {"has_credentials": False}
            else:
                if isinstance(data, dict) and "has_credentials" in data:
                    result = {"has_credentials": bool(data.get("has_credentials"))}
                else:
                    result = {"has_credentials": False}
    except httpx.HTTPStatusError as e:
        # Server returned an error status (non-2xx)
        logger.exception(MSG_EXCEPTION_OPENAI_CREDENTIALS)
        st.error(f"Failed to fetch OpenAI credentials status: {e.response.text}")
        result = None
    except httpx.RequestError as e:
        # Network / transport errors
        logger.exception(MSG_EXCEPTION_OPENAI_CREDENTIALS_NETWORK)
        st.error(f"Network error while fetching OpenAI credentials status: {e}")
        result = None

    return result


# ---- Log in and log out helpers ----


def build_login_url(scope_list: list[str] | None = None, *, force_prompt: bool = False) -> str:
    """
    Build an Auth0 /authorize URL using settings + provided scopes.
    If force_prompt=True, adds prompt=login to require credentials even if SSO is active.
    """
    domain = settings.auth0_domain
    audience = settings.auth0_api_audience  # already configured with trailing '/'
    redirect_uri = ensure_https(settings.auth0_redirect_uri)
    client_id = settings.auth0_client_id

    # Ensure openid/profile/email are present and preserve caller's order for extras.
    base_scopes = ["openid", "profile", "email"]
    extras = scope_list or []
    # Deduplicate while preserving order
    scopes = list(dict.fromkeys([*base_scopes, *extras]))
    scope = " ".join(scopes)

    query = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "audience": audience,
        "scope": scope,
    }
    if force_prompt:
        query["prompt"] = "login"

    url = f"https://{domain}/authorize?{urllib.parse.urlencode(query)}"
    if settings.is_verbose_mode:
        # Pick the right message for forced vs normal login
        msg = MSG_INFO_AUTH0_FORCE_LOGIN_URI if force_prompt else MSG_INFO_AUTH0_LOGIN_URI
        logger.debug(msg.format(uri=url))
    return url


def build_force_login_url(scope_list: list[str] | None = None) -> str:
    """Convenience wrapper for build_login_url(..., force_prompt=True)."""
    return build_login_url(scope_list=scope_list, force_prompt=True)


def build_logout_url(return_to: str | None = None, *, federated: bool = False) -> str:
    """
    Build an Auth0 /v2/logout URL. Make sure `return_to` is in Auth0 'Allowed Logout URLs'.
    If federated=True, append federated=true to attempt IdP logout as well (if supported).
    """
    dest = return_to or settings.frontend_domain or settings.auth0_redirect_uri
    client_id = settings.auth0_client_id
    _return_to = ensure_https(dest)

    base = (
        f"https://{settings.auth0_domain}{AUTH0_LOGOUT_PATH}"
        f"?client_id={urllib.parse.quote(client_id)}"
        f"&returnTo={urllib.parse.quote(_return_to, safe='')}"
    )
    url = f"{base}&federated=true" if federated else base
    if settings.is_verbose_mode:
        logger.debug(MSG_INFO_AUTH0_LOGOUT_URI.format(uri=url))
    return url
