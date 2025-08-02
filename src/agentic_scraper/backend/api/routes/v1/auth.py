import logging
import time
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.backend.config.messages import (
    MSG_WARNING_AUTH_CALLBACK_MISSING_CODE,
    MSG_DEBUG_AUTH_CALLBACK_CODE_RECEIVED,
    MSG_ERROR_AUTH_TOKEN_EXCHANGE_FAILED,
    MSG_ERROR_AUTH_RESPONSE_MISSING_TOKEN,
    MSG_DEBUG_AUTH_TOKEN_RECEIVED,
    MSG_DEBUG_AUTH_REDIRECT_URL,
    MSG_EXCEPTION_AUTH_CALLBACK_FAILURE,
    MSG_INFO_AUTH_CALLBACK_DURATION,
)

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


@router.get("/callback")
async def auth_callback(request: Request):
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

            if res.status_code != 200:
                logger.error(MSG_ERROR_AUTH_TOKEN_EXCHANGE_FAILED.format(
                    status=res.status_code,
                    body=res.text
                ))
                return RedirectResponse(f"{settings.frontend_domain}/?error=token_exchange_failed")

            token = res.json().get("access_token")

        if not token:
            logger.error(MSG_ERROR_AUTH_RESPONSE_MISSING_TOKEN)
            return RedirectResponse(f"{settings.frontend_domain}/?error=missing_token")

        logger.debug(MSG_DEBUG_AUTH_TOKEN_RECEIVED.format(token_preview=token[:10]))
        redirect_url = f"{settings.frontend_domain}/?token={token}"
        logger.debug(MSG_DEBUG_AUTH_REDIRECT_URL.format(redirect_url=redirect_url))
        return RedirectResponse(redirect_url)

    except Exception as e:
        logger.exception(MSG_EXCEPTION_AUTH_CALLBACK_FAILURE)
        return RedirectResponse(f"{settings.frontend_domain}/?error=token_exchange_failed")
    finally:
        duration = time.perf_counter() - start
        logger.info(MSG_INFO_AUTH_CALLBACK_DURATION.format(duration=duration))
