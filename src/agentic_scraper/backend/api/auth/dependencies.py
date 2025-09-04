"""
Auth dependencies for extracting and validating the current user from JWT tokens.

Endpoints / Dependencies:
- `get_current_user`: FastAPI dependency that verifies an Auth0-issued JWT and
  yields an `AuthUser` for downstream handlers.

Auth:
- Expects `Authorization: Bearer <JWT>` in the request.
- Signature and claims are verified using Auth0 JWKS (via `verify_jwt`), enforcing
  issuer and audience from settings. Failures yield HTTP 401; infra errors during
  JWKS retrieval surface as HTTP 503.

Response Models:
- `AuthUser` on success, with fields: `sub`, `email`, `name`, `scope`.

Error Codes & Status:
- 401: Missing/invalid token, malformed header, expired token, or bad claims.
- 503: JWKS retrieval failures (network or Auth0 availability).
- 500: Unexpected internal errors during verification flow.

Usage:
    from fastapi import Depends, APIRouter
    from agentic_scraper.backend.api.auth.dependencies import get_current_user
    from agentic_scraper.backend.api.models import AuthUser

    router = APIRouter()

    @router.get("/me")
    async def read_current_user(
        user: AuthUser = Depends(get_current_user)
    ) -> AuthUser:
        return user

Notes:
- This module is part of the public dependency surface; `__all__` is explicit.
- Logs are sampled to avoid excessive verbosity under load.
"""

import itertools
import logging

from fastapi import Depends, HTTPException, status
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

# This file is part of the public API surface for route dependencies.
__all__ = ["get_current_user"]

logger = logging.getLogger(__name__)

# Parse and enforce a Bearer token from the Authorization header.
# `auto_error=True` means FastAPI will raise a 403 before our handler if the
# header is missing or malformed (we still handle downstream verification).
auth_scheme = HTTPBearer(auto_error=True)

# Throttle occasional debug logs (e.g., every 50th call) to avoid noisy logs.
_auth_dep_counter = itertools.count()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> AuthUser:
    """
    Extract and verify the current user from a JWT token provided in the Authorization header.

    Internally verifies the token with Auth0's JWKS (via `verify_jwt`), validates required
    claims, and transforms the decoded payload into an `AuthUser`.

    Args:
        credentials (HTTPAuthorizationCredentials): Parsed Bearer token credentials
            provided by the `HTTPBearer` security scheme.

    Returns:
        AuthUser: Mapping with:
            - sub (OwnerSub): Stable subject identifier.
            - email (str | None): User email, if present.
            - name (str | None): Human-readable name, if present.
            - scope (str | None): Space-delimited OAuth scopes, if present.

    Raises:
        HTTPException: 401 if the token is invalid, expired, or missing required fields.
        HTTPException: Propagated 401 from `verify_jwt` for signature/claims failures.
        HTTPException: 500 if an unexpected error occurs during verification/decoding.

    Notes:
        - The function logs sensitive data sparingly; token values are sampled.
    """
    # Extract raw token string from credentials parsed by the auth scheme.
    token = credentials.credentials

    try:
        # Periodically emit a debug log with the token value (guarded by sampling).
        if next(_auth_dep_counter) % 50 == 0:
            logger.debug(MSG_DEBUG_VERIFYING_JWT_TOKEN.format(token=token))

        # Verify signature/claims and decode payload using Auth0 JWKS.
        payload = await verify_jwt(token)

    except JWTError as err:
        # Cryptographic decoding/claims errors raised by jose; convert to 401.
        logger.warning(MSG_WARNING_JWT_VERIFICATION_FAILED, exc_info=err)
        raise_unauthorized(err)

    except HTTPException as he:
        # Let verify_jwt's HTTP status pass through (e.g., 401 on invalid/expired token).
        if he.status_code == status.HTTP_401_UNAUTHORIZED:
            logger.warning(MSG_WARNING_JWT_VERIFICATION_FAILED, exc_info=he)
            raise
        # For other HTTP statuses, log and re-raise (e.g., 503 during JWKS fetch issues).
        logger.exception(MSG_ERROR_UNEXPECTED_EXCEPTION, exc_info=he)
        raise

    except Exception as e:
        # Any truly unexpected failure becomes a 500 to the client with logged context.
        logger.exception(MSG_ERROR_UNEXPECTED_EXCEPTION, exc_info=e)
        raise_internal_error(e)

    # Minimal required claim for identity; without it we cannot create an AuthUser.
    sub = payload.get("sub")
    if not sub:
        # Use standardized unauthorized helper to return a 401 with a clear message.
        raise_unauthorized(MSG_ERROR_MISSING_SUB_CLAIM)

    # Normalize/shape the response into our AuthUser model.
    # - OwnerSub.from_value coerces the raw 'sub' into our typed wrapper.
    # - Email/name are fetched using configured claim names, with sensible fallbacks.
    return {
        "sub": OwnerSub.from_value(payload["sub"]),
        "email": payload.get(CLAIM_EMAIL, payload.get("email")),
        "name": payload.get(CLAIM_NAME, payload.get("name")),
        "scope": payload.get("scope"),
    }
