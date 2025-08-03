"""
OAuth2 callback route for handling Auth0 authorization code exchange.

This module defines the `/callback` route, which is used in the Auth0 authorization
code flow. When a user completes login on Auth0, they are redirected back to this
endpoint with a `code` in the query string.

This route then:
- Exchanges the `code` for an access token via Auth0's `/oauth/token` endpoint.
- If successful, redirects the user to the frontend with the token appended.
- Logs errors and redirect with appropriate query parameters on failure.

Usage:
    Mounted under the API router (e.g., `/api/v1/auth/callback`) and triggered
    after user authentication completes via Auth0.
"""

import logging
import time

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

__all__ = ["auth_callback"]

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


@router.get("/callback")
async def auth_callback(request: Request) -> RedirectResponse:
    """
    Handle the Auth0 OAuth2 callback by exchanging the code for a JWT token.

    This route is hit after the user authenticates via Auth0 and is redirected
    back to the app with a `code` query parameter. It attempts to exchange the
    code for an access token, and then redirects the user back to the frontend
    with the token (or an error if the exchange fails).

    Args:
        request (Request): The incoming HTTP request containing query params.

    Returns:
        RedirectResponse: Redirect to the frontend with token or error in the URL.

    Raises:
        None explicitly. Any exceptions are caught and logged, and a redirect is issued.
    """
    start = time.perf_counter()

    code = request.query_params.get("code")
    if not code:
        logger.warning(MSG_WARNING_AUTH_CALLBACK_MISSING_CODE)
        return RedirectResponse(f"{settings.frontend_domain}/?error=missing_code")

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
        async with httpx.AsyncClient() as client:
            res = await client.post(token_url, json=payload)

            if res.status_code != HTTP_200_OK:
                logger.exception(
                    MSG_ERROR_AUTH_TOKEN_EXCHANGE_FAILED.format(
                        status=res.status_code, body=res.text
                    )
                )
                return RedirectResponse(f"{settings.frontend_domain}/?error=token_exchange_failed")

            token = res.json().get("access_token")

        if not token:
            logger.exception(MSG_ERROR_AUTH_RESPONSE_MISSING_TOKEN)
            return RedirectResponse(f"{settings.frontend_domain}/?error=missing_token")

        logger.debug(MSG_DEBUG_AUTH_TOKEN_RECEIVED.format(token_preview=token[:10]))
        redirect_url = f"{settings.frontend_domain}/?token={token}"
        logger.debug(MSG_DEBUG_AUTH_REDIRECT_URL.format(redirect_url=redirect_url))
        return RedirectResponse(redirect_url)

    except Exception:
        logger.exception(MSG_EXCEPTION_AUTH_CALLBACK_FAILURE)
        return RedirectResponse(f"{settings.frontend_domain}/?error=token_exchange_failed")
    finally:
        duration = time.perf_counter() - start
        logger.info(MSG_INFO_AUTH_CALLBACK_DURATION.format(duration=duration))
