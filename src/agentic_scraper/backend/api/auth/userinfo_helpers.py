import httpx
import logging

from agentic_scraper.backend.core.settings import get_settings


async def get_user_profile(access_token: str) -> dict:
    """
    Fetch user profile from Auth0's /userinfo endpoint using the access token.

    Args:
        access_token (str): A valid JWT access token.

    Returns:
        dict: User profile containing at least `name` and `email`.

    Raises:
        httpx.HTTPError: If the request fails or is unauthorized.
    """
    logger = logging.getLogger(__name__)
    settings = get_settings()
    userinfo_url = f"https://{settings.auth0_domain}/userinfo"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5.0,
            )
            response.raise_for_status()
            profile = response.json()
            logger.debug(f"Fetched user profile from /userinfo: {profile}")
            return profile
        
    except Exception as e:
        logger.warning(f"Failed to fetch user profile from /userinfo: {e}")
        return {}
