import logging

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from agentic_scraper.backend.api.auth.auth0_helpers import verify_jwt
from agentic_scraper.backend.api.models import AuthUser
from agentic_scraper.backend.api.utils.log_helpers import raise_internal_error, raise_unauthorized
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_UNEXPECTED_EXCEPTION,
    MSG_DEBUG_VERIFYING_JWT_TOKEN,
    MSG_WARNING_JWT_VERIFICATION_FAILED,
)

logger = logging.getLogger(__name__)
auth_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> AuthUser:
    """
    Extract and verify the current user from a JWT token.

    Args:
        credentials (HTTPAuthorizationCredentials): Bearer token extracted from the Authorization header.

    Returns:
        AuthUser: Parsed user object from the decoded JWT token.

    Raises:
        HTTPException: If the token is invalid, expired, or verification fails.
    """
    token = credentials.credentials

    try:
        logger.debug(MSG_DEBUG_VERIFYING_JWT_TOKEN.format(token=token))  # Remove or redact in production
        payload = await verify_jwt(token)

        user_data: AuthUser = {
            "sub": payload.get("sub"),
            "email": payload.get("https://agentic.scraper/email", payload.get("email")),
            "name": payload.get("https://agentic.scraper/name", payload.get("name")),
            "scope": payload.get("scope", ""),
        }

        if not user_data["sub"]:
            raise_unauthorized("Missing 'sub' in token payload")
        return user_data

    except JWTError as err:
        logger.warning(MSG_WARNING_JWT_VERIFICATION_FAILED, exc_info=err)
        raise raise_unauthorized(err)

    except Exception as e:
        logger.exception(MSG_ERROR_UNEXPECTED_EXCEPTION, exc_info=e)
        raise raise_internal_error(e)
