"""
OAuth2 callback route for handling Auth0 authorization code exchange.

Flow:
- Receives `code` as a query param after Auth0 login.
- Exchanges `code` for an access token via Auth0 `/oauth/token`.
- Redirects to the frontend with either `?token=...` or `?error=...`.
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

__all__ = ["auth_callback"]

router = APIRouter(prefix="/auth", tags=["Auth"])
settings = get_settings()
logger = logging.getLogger(__name__)

# Conservative network timeout for the token exchange
_TOKEN_TIMEOUT_SECONDS: Final[float] = 10.0


def _redirect_with_error(error_code: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.frontend_domain}/?error={error_code}")


@router.get("/callback")
async def auth_callback(request: Request) -> RedirectResponse:
    """
    Handle the Auth0 OAuth2 callback by exchanging the `code` for an access token.
    Always responds with a redirect to the frontend, carrying either ?token=... or ?error=...
    """
    start = time.perf_counter()

    code = request.query_params.get("code")
    if not code:
        logger.warning(MSG_WARNING_AUTH_CALLBACK_MISSING_CODE)
        return _redirect_with_error("missing_code")

    # Safe to log in DEBUG; code is short-lived
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
        # OAuth2 token endpoints typically expect form-encoded bodies
        async with httpx.AsyncClient(timeout=_TOKEN_TIMEOUT_SECONDS) as client:
            res = await client.post(
                token_url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if res.status_code != HTTP_200_OK:
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

        logger.debug(MSG_DEBUG_AUTH_TOKEN_RECEIVED.format(token_preview=str(token)[:10]))
        redirect_url = f"{settings.frontend_domain}/?token={token}"
        logger.debug(MSG_DEBUG_AUTH_REDIRECT_URL.format(redirect_url=redirect_url))
        return RedirectResponse(redirect_url)

    except Exception:
        # Broad catch to ensure we always redirect with an error
        logger.exception(MSG_EXCEPTION_AUTH_CALLBACK_FAILURE)
        return _redirect_with_error("token_exchange_failed")

    finally:
        duration = time.perf_counter() - start
        logger.info(MSG_INFO_AUTH_CALLBACK_DURATION.format(duration=duration))
