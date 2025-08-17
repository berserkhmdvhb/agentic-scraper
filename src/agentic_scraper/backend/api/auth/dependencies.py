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

import itertools
import logging

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from agentic_scraper.backend.api.auth.auth0_helpers import verify_jwt
from agentic_scraper.backend.api.models import AuthUser, OwnerSub
from agentic_scraper.backend.api.utils.log_helpers import (
    raise_internal_error,
    raise_unauthorized,
)
from agentic_scraper.backend.config.constants import CLAIM_EMAIL, CLAIM_NAME
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_VERIFYING_JWT_TOKEN,
    MSG_ERROR_MISSING_SUB_CLAIM,
    MSG_ERROR_UNEXPECTED_EXCEPTION,
    MSG_WARNING_JWT_VERIFICATION_FAILED,
)

__all__ = ["get_current_user"]

logger = logging.getLogger(__name__)
auth_scheme = HTTPBearer(auto_error=True)
_auth_dep_counter = itertools.count()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> AuthUser:
    """
    Extract and verify the current user from a JWT token provided in the Authorization header.

    Internally verifies the token with Auth0's JWKS, validates required claims,
    and transforms the decoded payload into an `AuthUser`.

    Args:
        credentials (HTTPAuthorizationCredentials): The bearer token from the Authorization header.

    Returns:
        AuthUser: Dictionary containing 'sub', 'email', 'name', and 'scope'.

    Raises:
        HTTPException: If the token is missing required fields or is invalid (401).
        HTTPException: If any unexpected error occurs during decoding (500).
    """
    token = credentials.credentials

    try:
        if next(_auth_dep_counter) % 50 == 0:
            logger.debug(MSG_DEBUG_VERIFYING_JWT_TOKEN.format(token=token))
        payload = await verify_jwt(token)

    except JWTError as err:
        logger.warning(MSG_WARNING_JWT_VERIFICATION_FAILED, exc_info=err)
        raise_unauthorized(err)

    except Exception as e:
        logger.exception(MSG_ERROR_UNEXPECTED_EXCEPTION, exc_info=e)
        raise_internal_error(e)

    sub = payload.get("sub")
    if not sub:
        raise_unauthorized(MSG_ERROR_MISSING_SUB_CLAIM)

    return {
        "sub": OwnerSub.from_value(payload["sub"]),
        "email": payload.get(CLAIM_EMAIL, payload.get("email")),
        "name": payload.get(CLAIM_NAME, payload.get("name")),
        "scope": payload.get("scope", ""),
    }
