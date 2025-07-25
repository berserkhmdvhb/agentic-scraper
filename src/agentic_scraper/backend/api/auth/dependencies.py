from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agentic_scraper.backend.api.auth.auth0_helpers import verify_jwt

auth_scheme = HTTPBearer(auto_error=True)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = None) -> dict[str, Any]:
    if credentials is None:
        credentials = Depends(auth_scheme)
    token = credentials.credentials
    return verify_jwt(token)
