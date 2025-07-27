import logging
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from agentic_scraper.backend.api.auth.auth0_helpers import verify_jwt
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_INTERNAL_SERVER,
    MSG_ERROR_INVALID_TOKEN,
    MSG_ERROR_MISSING_SCOPES,
    MSG_ERROR_UNEXPECTED_EXCEPTION,
    MSG_INFO_USER_AUTHORIZED,  # New constant for user authorization log
    MSG_WARNING_INSUFFICIENT_PERMISSIONS,
)

# Initialize logger
logger = logging.getLogger(__name__)

auth_scheme = HTTPBearer(auto_error=True)

def raise_forbidden(required_scopes: list[str]) -> None:
    """
    Raise a 403 Forbidden HTTPException due to insufficient permissions.

    Logs a warning and raises an exception with the appropriate status code and
    error message.

    Args:
        required_scopes (list[str]): List of required scopes that the user needs.
    """
    logger.warning(MSG_WARNING_INSUFFICIENT_PERMISSIONS.format(scopes=required_scopes))
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=MSG_ERROR_MISSING_SCOPES.format(scopes=required_scopes),
        headers={"WWW-Authenticate": "Bearer"},
    )

def raise_unauthorized(err: JWTError) -> None:
    """
    Raise a 401 Unauthorized HTTPException due to invalid or expired JWT.

    Logs the error message and raises an exception with the appropriate status code.

    Args:
        err (JWTError): The exception raised during the JWT verification process.
    """
    logger.exception(MSG_ERROR_INVALID_TOKEN.format(error=str(err)))
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    ) from err

def raise_internal_error(e: Exception) -> None:
    """
    Raise a 500 Internal Server Error HTTPException.

    Logs the error message and raises an exception with the appropriate status code
    for unexpected issues.

    Args:
        e (Exception): The exception encountered during the JWT verification process.
    """
    logger.exception(MSG_ERROR_INTERNAL_SERVER.format(error=str(e)), exc_info=e)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error during token validation",
        headers={"WWW-Authenticate": "Bearer"},
    ) from e

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    required_scopes: list[str] | None = None
) -> dict[str, Any]:
    """
    Extract and verify the current user from a JWT token, checking for required scopes.

    If the token is valid and the user has the necessary scopes, returns the decoded JWT
    payload representing the authenticated user.

    Args:
        credentials (HTTPAuthorizationCredentials):
            The authorization header parsed by FastAPI. Injected via `Depends`.
        required_scopes (list[str] | None):
            List of scopes required for the action. Defaults to None.

    Returns:
        dict[str, Any]: The decoded JWT payload representing the authenticated user.

    Raises:
        HTTPException:
            If the token is missing, invalid, expired, or doesn't have the required scope.
    """
    if required_scopes is None:
        required_scopes = []  # Default to empty list if not provided

    # Extract the token from the credentials object
    token = credentials.credentials

    try:
        # Directly return the result of JWT token verification
        payload = await verify_jwt(token)

        # If required_scopes is not empty, check if the scope claim contains necessary scopes
        if required_scopes:
            user_scopes = payload.get("scope", [])
            if not any(scope in user_scopes for scope in required_scopes):
                # Use helper function for the forbidden error
                raise_forbidden(required_scopes)
            # Return the payload if required scopes are met
            return payload
        # Log for authorization success
        logger.info(MSG_INFO_USER_AUTHORIZED)
        # Return the payload if no required scopes are provided
        # ruff: noqa: TRY300
        return payload

    except JWTError as err:
        raise_unauthorized(err)
    # Catching only JWT-specific errors
    except Exception as e:
        logger.exception(MSG_ERROR_UNEXPECTED_EXCEPTION, exc_info=e)
        raise_internal_error(e)

    # Fallback return in case of no valid flow
    # (e.g., if the function is left without return or error handling)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected error"
    )
