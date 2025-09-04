"""
Scope validation helpers for Auth0-based authentication.

Responsibilities:
- Normalize and validate OAuth2 scope claims from decoded JWT payloads.
- Enforce required scopes within route handlers via a small helper.

Public API:
- `check_required_scopes`: Validate that a user's decoded JWT payload includes all required scopes.
- `auth_scheme`: Standard FastAPI HTTP Bearer scheme for use in route dependencies.

Usage:
    from fastapi import Depends
    from agentic_scraper.backend.api.auth.scope_helpers import check_required_scopes, auth_scheme
    from agentic_scraper.backend.api.auth.dependencies import get_current_user
    from agentic_scraper.backend.api.models import AuthUser, RequiredScopes

    @router.get("/admin", dependencies=[Depends(auth_scheme)])
    def read_admin(user: AuthUser = Depends(get_current_user)) -> dict:
        check_required_scopes(user, {RequiredScopes.SCRAPES_READ})
        return {"ok": True}

Notes:
- Scopes are defined centrally in `agentic_scraper.backend.api.models.RequiredScopes`.
- The "scope" claim may be a space-delimited string, a list of strings, or absent.
  Use `validate_scopes_input` to normalize shapes consistently.
"""

import logging

from fastapi.security import HTTPBearer

from agentic_scraper.backend.api.models import AuthUser, RequiredScopes
from agentic_scraper.backend.api.utils.log_helpers import raise_forbidden
from agentic_scraper.backend.config.messages import MSG_DEBUG_MISSING_SCOPES
from agentic_scraper.backend.utils.validators import validate_scopes_input

logger = logging.getLogger(__name__)

# Standard FastAPI HTTP Bearer scheme. Typically used in combination with
# `Depends(auth_scheme)` or within a router's `dependencies=[Depends(auth_scheme)]`.
# Keeping this here allows route modules to import a consistent scheme definition.
auth_scheme = HTTPBearer(auto_error=True)


def check_required_scopes(payload: AuthUser, required_scopes: set[RequiredScopes]) -> None:
    """
    Validate that the token payload contains all required scopes.

    This function normalizes the "scope" claim (which may be a string, list, or None),
    converts it into a set, and checks it against the required scopes. If any required
    scopes are missing, an HTTP 403 Forbidden is raised.

    Args:
        payload (AuthUser): Decoded JWT payload containing user information,
            including the "scope" claim.
        required_scopes (set[RequiredScopes]): Set of scopes that the route
            requires for access.

    Returns:
        None

    Raises:
        HTTPException: 403 if any of the required scopes are missing from the payload.

    Examples:
        >>> payload = {"scope": "read:users write:users"}
        >>> check_required_scopes(payload, {RequiredScopes.SCRAPES_READ})
        # Raises HTTPException(403) if SCRAPES_READ not present.

    Notes:
        - `RequiredScopes` lives in `agentic_scraper.backend.api.models`. Each enum member's
          `.value` is the actual wire scope string configured in Auth0.
        - Logs missing scopes at debug level for visibility without exposing sensitive info.
    """
    # Normalize the "scope" claim into a list[str].
    # Example: "read:users write:users" -> ["read:users", "write:users"]
    user_scopes = validate_scopes_input(payload.get("scope"))

    # Convert list -> set for O(1) membership checks on each required scope.
    user_scopes_set: set[str] = set(user_scopes)

    # Identify which required scopes are missing from the user's set.
    missing_scopes = [
        scope.value for scope in required_scopes if scope.value not in user_scopes_set
    ]

    if missing_scopes:
        # Log at debug level for visibility without polluting normal logs.
        logger.debug(
            MSG_DEBUG_MISSING_SCOPES.format(
                missing_scopes=" ".join(missing_scopes),
                user_scopes=" ".join(user_scopes),
            )
        )
        # Abort request with 403 Forbidden. We surface just the missing scopes by name.
        raise_forbidden(required_scopes=missing_scopes)
