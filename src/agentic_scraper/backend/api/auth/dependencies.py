"""
Auth dependencies for extracting and validating the current user from JWT tokens.

This module defines the FastAPI dependency `get_current_user`, which is used to
authenticate incoming requests based on Auth0-issued JWT tokens. It integrates
with the `auth0_helpers` module to verify tokens and decode claims. The decoded
payload is transformed into an `AuthUser` object used across API routes for
authorization and identity.

Usage:
    Inject `get_current_user` as a dependency in FastAPI routes to enforce
    authenticated access. The returned `AuthUser` contains fields like `sub`,
    `email`, `name`, and `scope`, which can be used to enforce role-based
    logic or user-specific behavior.

Example:
    @router.get("/me")
    async def read_current_user(user: AuthUser = Depends(get_current_user)):
        return user
"""

import logging

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from agentic_scraper.backend.api.auth.auth0_helpers import verify_jwt
from agentic_scraper.backend.api.models import AuthUser
from agentic_scraper.backend.api.utils.log_helpers import (
    raise_internal_error,
    raise_unauthorized,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_VERIFYING_JWT_TOKEN,
    MSG_ERROR_UNEXPECTED_EXCEPTION,
    MSG_WARNING_JWT_VERIFICATION_FAILED,
)

__all__ = ["get_current_user"]

logger = logging.getLogger(__name__)
auth_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> AuthUser:
    """
    Extract and verify the current user from a JWT token provided in the Authorization header.

    This function uses the FastAPI `Depends` system to extract a bearer token from
    the HTTP Authorization header. It then verifies the token using Auth0's JSON
    Web Key Set (JWKS) and decodes the payload into an `AuthUser` structure.

    Args:
        credentials (HTTPAuthorizationCredentials):
            The bearer token extracted by FastAPI from the incoming request's
            Authorization header.

    Returns:
        AuthUser:
            A dictionary-like object containing the user's `sub`, `email`, `name`, and `scope`.

    Raises:
        HTTPException (401): If the token is missing required fields or is invalid.
        HTTPException (500): If any unexpected error occurs during decoding.
    """
    token = credentials.credentials

    try:
        logger.debug(MSG_DEBUG_VERIFYING_JWT_TOKEN.format(token=token))
        payload = await verify_jwt(token)

        user_data: AuthUser = {
            "sub": payload.get("sub"),
            "email": payload.get("https://agentic.scraper/email", payload.get("email")),
            "name": payload.get("https://agentic.scraper/name", payload.get("name")),
            "scope": payload.get("scope", ""),
        }

        if not user_data["sub"]:
            raise_unauthorized("Missing 'sub' in token payload")
        else:
            return user_data

    except JWTError as err:
        logger.warning(MSG_WARNING_JWT_VERIFICATION_FAILED, exc_info=err)
        raise_unauthorized(err)

    except Exception as e:
        logger.exception(MSG_ERROR_UNEXPECTED_EXCEPTION, exc_info=e)
        raise_internal_error(e)
