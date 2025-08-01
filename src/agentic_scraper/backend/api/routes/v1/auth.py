import logging
import time
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from agentic_scraper.backend.core.settings import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


@router.get("/callback")
async def auth_callback(request: Request):
    start = time.perf_counter()

    code = request.query_params.get("code")
    if not code:
        logger.warning("❌ Missing 'code' in query params")
        return RedirectResponse(f"{settings.frontend_domain}/?error=missing_code")

    logger.debug(f"🔁 Auth0 code received in callback: {code}")

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
                logger.error(
                    f"❌ Auth0 token exchange failed. Status: {res.status_code}, Body: {res.text}"
                )
                return RedirectResponse(f"{settings.frontend_domain}/?error=token_exchange_failed")

            token = res.json().get("access_token")

        if not token:
            logger.error("❌ Auth0 response missing access_token")
            return RedirectResponse(f"{settings.frontend_domain}/?error=missing_token")

        logger.debug(f"✅ Access token received: {token[:10]}... [truncated]")
        redirect_url = f"{settings.frontend_domain}/?token={token}"
        logger.debug(f"🔁 Redirecting to frontend with token in URL: {redirect_url}")
        return RedirectResponse(redirect_url)

    except Exception as e:
        logger.exception("❌ Token exchange failed during Auth0 callback")
        return RedirectResponse(f"{settings.frontend_domain}/?error=token_exchange_failed")
    finally:
        duration = time.perf_counter() - start
        logger.info(f"✅ Auth0 callback completed in {duration:.2f}s")
