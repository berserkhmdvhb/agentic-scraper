"""
OAuth2 callback route for handling Auth0 authorization code exchange.

Endpoints / Dependencies:
- `GET /auth/callback` (`auth_callback`): Exchanges `code` for an access token
  and redirects to the frontend with `?token=...` or `?error=...`.

Auth:
- Uses Auth0 OAuth2 Authorization Code (with PKCE on the user-agent flow).
- Token exchange performed against `https://<AUTH0_DOMAIN>/oauth/token`.

Response Models:
- None; always responds with a `RedirectResponse`.

Error Codes & Status:
- Redirects with `?error=missing_code` when the `code` query param is absent.
- Redirects with `?error=token_exchange_failed` on non-200 Auth0 responses or exceptions.
- Redirects with `?error=missing_token` if the JSON body lacks `access_token`.

Usage:
    from fastapi import APIRouter
    from agentic_scraper.backend.api.routes.auth import router

    app.include_router(router)

Notes:
- The token exchange timeout is conservative (10s).
- Errors are redirected to the frontend using `?error=<code>` (no 5xx leaks to browser).
- Access tokens are never fully logged; only a short preview is emitted in DEBUG.
"""

from __future__ import annotations

import logging
import time
from typing import Final

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_200_OK

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_AUTH_CALLBACK_CODE_RECEIVED,
    MSG_DEBUG_AUTH_REDIRECT_URL,
    MSG_DEBUG_AUTH_TOKEN_RECEIVED,
    MSG_ERROR_AUTH_RESPONSE_MISSING_TOKEN,
    MSG_ERROR_AUTH_TOKEN_EXCHANGE_FAILED,
    MSG_EXCEPTION_AUTH_CALLBACK_FAILURE,
    MSG_INFO_AUTH_CALLBACK_DURATION,
    MSG_WARNING_AUTH_CALLBACK_MISSING_CODE,
)
from agentic_scraper.backend.core.settings import get_settings

__all__ = ["auth_callback", "router"]

router = APIRouter(prefix="/auth", tags=["Auth"])
settings = get_settings()
logger = logging.getLogger(__name__)

# Conservative network timeout for the token exchange (seconds).
# Keep tight to avoid hanging the browser redirect for long.
_TOKEN_TIMEOUT_SECONDS: Final[float] = 10.0


def _redirect_with_error(error_code: str) -> RedirectResponse:
    """
    Build a redirect response back to the frontend with an error code.

    Args:
        error_code (str): Short, URL-safe error identifier (e.g., "missing_code").

    Returns:
        RedirectResponse: Redirect to `<frontend_domain>/?error=<error_code>`.
    """
    return RedirectResponse(f"{settings.frontend_domain}/?error={error_code}")


@router.get("/callback")
async def auth_callback(request: Request) -> RedirectResponse:
    """
    Handle the Auth0 OAuth2 callback: exchange `code` for an access token, then redirect.

    Always responds with a redirect to the frontend, carrying either `?token=...`
    on success or `?error=...` on failure.

    Args:
        request (Request): Incoming request containing the `code` query parameter.

    Returns:
        RedirectResponse: Redirect to the frontend with either `token` or `error` in the query.

    Notes:
        - The `code` is short-lived; we only log it at DEBUG level.
        - Any exception results in a best-effort redirect to the frontend with an error.
    """
    start = time.perf_counter()

    code = request.query_params.get("code")
    if not code:
        logger.warning(MSG_WARNING_AUTH_CALLBACK_MISSING_CODE)
        return _redirect_with_error("missing_code")

    # Safe to log at DEBUG; the code is short-lived and not a bearer credential.
    logger.debug(MSG_DEBUG_AUTH_CALLBACK_CODE_RECEIVED.format(code=code))

    token_url = f"https://{settings.auth0_domain}/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": settings.auth0_client_id,
        "client_secret": settings.auth0_client_secret,
        "code": code,
        "redirect_uri": settings.auth0_redirect_uri,
    }

    try:
        # OAuth2 token endpoints typically expect application/x-www-form-urlencoded bodies.
        async with httpx.AsyncClient(timeout=_TOKEN_TIMEOUT_SECONDS) as client:
            res = await client.post(
                token_url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if res.status_code != HTTP_200_OK:
                # Include status and body (may contain helpful error context from Auth0).
                logger.exception(
                    MSG_ERROR_AUTH_TOKEN_EXCHANGE_FAILED.format(
                        status=res.status_code, body=res.text
                    )
                )
                return _redirect_with_error("token_exchange_failed")

            token = res.json().get("access_token")

        if not token:
            logger.exception(MSG_ERROR_AUTH_RESPONSE_MISSING_TOKEN)
            return _redirect_with_error("missing_token")

        # Only preview a small prefix of the token in logs to avoid leaks.
        logger.debug(MSG_DEBUG_AUTH_TOKEN_RECEIVED.format(token_preview=str(token)[:10]))

        redirect_url = f"{settings.frontend_domain}/?token={token}"
        logger.debug(MSG_DEBUG_AUTH_REDIRECT_URL.format(redirect_url=redirect_url))
        return RedirectResponse(redirect_url)

    except Exception:
        # Broad catch to ensure we always redirect with an error, not a 5xx.
        logger.exception(MSG_EXCEPTION_AUTH_CALLBACK_FAILURE)
        return _redirect_with_error("token_exchange_failed")

    finally:
        duration = time.perf_counter() - start
        logger.info(MSG_INFO_AUTH_CALLBACK_DURATION.format(duration=duration))
