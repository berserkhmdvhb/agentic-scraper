"""
Low-level authentication helpers for the Streamlit frontend.

Responsibilities:
- Extract a JWT from URL query parameters or Streamlit session state.
- Build Authorization headers for backend calls.
- Construct the backend API base URL (versioned).
- Fetch authenticated user profile and (masked) OpenAI credentials.
- Generate Auth0 login and logout URLs for the UI layer.

Public API:
- `ensure_https`: Normalize domains/hosts to https:// scheme.
- `api_base`: Build the versioned backend API base URL.
- `get_jwt_token_from_url_or_session`: Resolve/validate JWT and store in session.
- `build_auth_headers`: Construct Authorization header from session JWT.
- `fetch_user_profile`: Retrieve and stash user profile in session state.
- `fetch_openai_credentials`: Retrieve masked OpenAI creds and stash a preview.
- `fetch_openai_credentials_status`: Check whether creds exist (boolean).
- `build_login_url` / `build_force_login_url`: Create Auth0 authorize URLs.
- `build_logout_url`: Create Auth0 logout URL with optional federated flag.

Config:
- Uses values from `Settings` (`auth0_domain`, `auth0_client_id`, `auth0_api_audience`,
  `auth0_redirect_uri`, `frontend_domain`, `backend_domain`, `is_verbose_mode`).
- API version sourced from `agentic_scraper.__api_version__`.

Operational:
- Logging: Uses message constants and avoids leaking sensitive tokens (masked preview).
- Network: Synchronous `httpx` calls with conservative timeouts; handled errors surface to UI.

Usage:
    # Resolve token and build headers
    token = get_jwt_token_from_url_or_session()
    headers = build_auth_headers()

    # Fetch user info and masked OpenAI credentials
    fetch_user_profile()
    fetch_openai_credentials()

Notes:
- UI rendering and widget logic live in `ui_auth.py`;
    this module intentionally avoids UI layout.
- Query param handling clears the URL after processing
    `?token=...` to prevent re-processing on reruns.
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
    """
    Normalize a domain/host string to an HTTPS URL.

    If the input already starts with `http://` or `https://`, it is returned unchanged.
    Otherwise, `https://` is prepended. Empty inputs return an empty string.

    Args:
        domain (str): A domain, host, or URL (may be empty).

    Returns:
        str: The normalized URL (or an empty string if `domain` is empty).

    Examples:
        ensure_https("example.com")         # -> "https://example.com"
        ensure_https("https://x.ngrok.app") # -> "https://x.ngrok.app"

    Notes:
        - This function does not validate the domain itself and does not append slashes.
    """
    if not domain:
        return ""
    if domain.startswith(("http://", "https://")):
        return domain
    return "https://" + domain


def api_base() -> str:
    """
    Build the versioned backend API base URL using `settings.backend_domain`.

    Returns:
        str: Base like "https://backend.example.com/api/v1"; empty string if not configured.

    Examples:
        # Assuming backend_domain="https://x.ngrok.app" and api_version="v1":
        api_base()  # -> "https://x.ngrok.app/api/v1"

    Notes:
        - This function uses the runtime `api_version` constant imported from the package root.
    """
    base = (settings.backend_domain or "").rstrip("/")
    if not base:
        return ""
    if not base.startswith("http"):
        base = "https://" + base
    return f"{base}/api/{api_version}"


def get_jwt_token_from_url_or_session() -> str | None:
    """
    Extract a JWT from the URL query (`?token=...`) or from `st.session_state`.

    Behavior:
      - If a token is found in the URL, validate its shape (`header.payload.signature`),
        set `st.session_state["auth_pending"] = True`, save it to `st.session_state["jwt_token"]`,
        log a masked preview, and clear the query params (preventing re-processing on reruns).
      - If no URL token exists, fall back to `st.session_state["jwt_token"]`.
      - If nothing is found, a warning is logged and `None` is returned.

    Returns:
        str | None: The JWT if found and well-formed; otherwise `None`.

    Examples:
        # On a first run with URL `...?token=eyJ...`
        token = get_jwt_token_from_url_or_session()  # -> "eyJ..."

        # On subsequent reruns (after clearing the URL), it is read from session_state
        token = get_jwt_token_from_url_or_session()  # -> same token

    Notes:
        - Only a basic three-part check is performed;
            cryptographic verification happens in the backend.
        - Streamlit's `st.query_params.clear()`
            is used to avoid repeated processing when the script reruns.
    """
    token = st.query_params.get("token")

    if token:
        # Streamlit can provide query param as a list—normalize to a single string.
        jwt_token = token[0] if isinstance(token, list) else token
        if isinstance(jwt_token, str):
            jwt_token = jwt_token.strip()

        # Basic shape check: "header.payload.signature"
        if isinstance(jwt_token, str) and len(jwt_token.split(".")) == EXPECTED_JWT_PARTS:
            st.session_state["auth_pending"] = True
            st.session_state["jwt_token"] = jwt_token
            # Log a masked preview to avoid leaking the full token
            preview = f"{jwt_token[:10]}…"
            logger.debug(MSG_DEBUG_JWT_FROM_URL.format(token=preview))
            st.query_params.clear()  # prevent re-processing on rerun
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
    """
    Construct Authorization headers from the session JWT.

    Returns:
        dict[str, str]: Headers containing `Authorization: Bearer <jwt>`.

    Raises:
        RuntimeError: If no JWT is present in `st.session_state["jwt_token"]`.

    Examples:
        headers = build_auth_headers()
        # -> {"Authorization": "Bearer eyJ..."}
    """
    jwt = st.session_state.get("jwt_token")
    if not jwt:
        # Use a message constant for consistency with backend logging
        raise RuntimeError(MSG_ERROR_USER_NOT_AUTHENTICATED)
    return {"Authorization": f"Bearer {jwt}"}


# --------- Backend calls (sync) ---------


def fetch_user_profile(on_unauthorized: Callable[[], None] | None = None) -> None:
    """
    Fetch the authenticated user's profile (`GET /user/me`) and stash it in session state.

    On success:
        Sets `st.session_state["user_info"] = <json response>` and logs success.

    On 401:
        Shows a warning, optionally invokes `on_unauthorized()`, and returns.

    Args:
        on_unauthorized (Callable[[], None] | None): Optional callback invoked when a 401
            is returned (e.g., to clear state or redirect).

    Returns:
        None

    Notes:
        - Uses `build_auth_headers()` and `api_base()`; surfaces errors to the UI via `st.error()`.
        - Network and HTTP errors are logged with message constants for consistency.
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
    Fetch the user's OpenAI credentials preview (`GET /user/openai-credentials`).

    Behavior:
        - Writes a **masked preview** into `st.session_state["openai_credentials_preview"]`.
        - Does **not** overwrite any real credentials stored elsewhere.
        - On 401, shows a warning, optionally invokes `on_unauthorized()`, and returns.

    Args:
        on_unauthorized (Callable[[], None] | None): Optional callback invoked on 401.

    Returns:
        None

    Notes:
        - The API returns (possibly empty) keys; inputs are wrapped into `OpenAIConfig`.
        - Network and HTTP errors are logged with message constants.
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
    Check whether OpenAI credentials exist (`GET /user/openai-credentials/status`).

    Args:
        on_unauthorized (Callable[[], None] | None): Optional callback invoked on 401.

    Returns:
        dict[str, bool] | None: A dict like `{"has_credentials": True/False}` if successful,
            `None` on auth/network errors.

    Examples:
        status = fetch_openai_credentials_status()
        if status and status.get("has_credentials"):
            st.session_state["has_openai_creds"] = True

    Notes:
        - Does not mutate session state automatically; lets callers decide on flags/UX.
        - JSON parsing errors are treated as "no credentials" rather than hard failures.
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
    Build an Auth0 `/authorize` URL using settings and provided scopes.

    Args:
        scope_list (list[str] | None): Additional scopes to request. The base set
            `["openid", "profile", "email"]` is always included; extras are de-duplicated
            while preserving order.
        force_prompt (bool): If True, appends `prompt=login` to force credentials entry
            even if SSO is active.

    Returns:
        str: A fully formed Auth0 authorize URL.

    Examples:
        url = build_login_url(["read:user_profile"])
        force_url = build_login_url(["read:user_profile"], force_prompt=True)

    Notes:
        - Audience must be configured correctly in settings (often requires trailing slash).
        - In verbose mode, logs the final URL with a message constant.
    """
    domain = settings.auth0_domain
    audience = settings.auth0_api_audience  # already configured with trailing '/'
    redirect_uri = ensure_https(settings.auth0_redirect_uri)
    client_id = settings.auth0_client_id

    # Ensure openid/profile/email are present and preserve caller's order for extras.
    base_scopes = ["openid", "profile", "email"]
    extras = scope_list or []
    # Deduplicate while preserving order using dict insertion order.
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
    """
    Convenience wrapper to force an Auth0 credentials prompt.

    Args:
        scope_list (list[str] | None): Additional scopes to request.

    Returns:
        str: Same as `build_login_url(..., force_prompt=True)`.

    Examples:
        url = build_force_login_url(["read:user_profile"])
    """
    return build_login_url(scope_list=scope_list, force_prompt=True)


def build_logout_url(return_to: str | None = None, *, federated: bool = False) -> str:
    """
    Build an Auth0 `/v2/logout` URL.

    Args:
        return_to (str | None): Destination URL after logout. Must be whitelisted under
            "Allowed Logout URLs" in the Auth0 application settings. If not provided,
            falls back to `settings.frontend_domain` or `settings.auth0_redirect_uri`.
        federated (bool): When True, appends `federated=true` to also attempt IdP logout,
            if supported by the identity provider.

    Returns:
        str: A fully formed Auth0 logout URL.

    Examples:
        url = build_logout_url("https://app.example.com")
        fed = build_logout_url("https://app.example.com", federated=True)

    Notes:
        - `return_to` is normalized with `ensure_https`.
        - In verbose mode, logs the final URL using a message constant.
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
