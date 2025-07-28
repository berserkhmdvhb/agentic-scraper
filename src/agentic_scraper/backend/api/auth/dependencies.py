import logging

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from agentic_scraper.backend.api.auth.auth0_helpers import verify_jwt
from agentic_scraper.backend.api.models import AuthUser
from agentic_scraper.backend.api.utils.log_helpers import raise_internal_error, raise_unauthorized
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_UNEXPECTED_EXCEPTION,
)

# Initialize logger
logger = logging.getLogger(__name__)

auth_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> AuthUser | None:
    """
    Extract and verify the current user from a JWT token.

    Args:
        credentials (HTTPAuthorizationCredentials): The authorization header parsed by FastAPI.

    Returns:
        AuthUser: The decoded JWT payload representing the authenticated user.
        None: If the token is invalid or expired.

    Raises:
        HTTPException: If the token is invalid or expired.
    """
    token = credentials.credentials

    try:
        # Decode the JWT token and verify its validity
        payload = await verify_jwt(token)
        user_data: AuthUser = {
            "sub": payload["sub"],  # User identifier (subject)
            "email": payload.get("email"),
            "name": payload.get("name"),
            "scope": payload.get("scope", ""),  # Extract scope from the token
        }

    except JWTError as err:
        raise_unauthorized(err)
        return None  # Ensure returning None after exception
    except Exception as e:
        logger.exception(MSG_ERROR_UNEXPECTED_EXCEPTION, exc_info=e)
        raise_internal_error(e)
        return None  # Ensure returning None after exception
    else:
        # Return the payload if everything is valid
        return user_data
