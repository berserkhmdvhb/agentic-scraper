from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agentic_scraper.backend.api.auth.auth0_helpers import verify_jwt

auth_scheme = HTTPBearer(auto_error=True)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = None) -> dict[str, Any]:
    """
    Dependency for extracting and verifying the current user from a JWT.

    This function is designed to be used with FastAPI's `Depends` system.
    It:
    - Extracts the bearer token from the Authorization header
    - Verifies the token using Auth0 public keys
    - Returns the decoded payload as the current user

    Args:
        credentials (HTTPAuthorizationCredentials | None):
            The authorization header parsed by FastAPI. Injected via `Depends`.

    Returns:
        dict[str, Any]: The decoded JWT payload representing the authenticated user.

    Raises:
        HTTPException: If the token is missing or invalid.
    """
    if credentials is None:
        credentials = Depends(auth_scheme)
    token = credentials.credentials
    return verify_jwt(token)
