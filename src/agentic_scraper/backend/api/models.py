"""
Lightweight API schemas used by authentication and route dependencies.

Models:
- `OwnerSub`: Nominal wrapper over the Auth0 subject string (e.g., "auth0|abc123").
- `AuthUser`: TypedDict shape of the authenticated user passed to handlers.
- `RequiredScopes`: Enum of OAuth scopes enforced by endpoints.

Serialization:
- Types are simple and intended for in-process use (not Pydantic models here).
- `OwnerSub` is a `str` subclass, so it serializes as a normal string.

Validation & Defaults:
- `OwnerSub.from_value` performs minimal format checking ("provider|id").
  Tighten as needed for your Auth0 tenant conventions.

Usage:
    from agentic_scraper.backend.api.models import AuthUser, OwnerSub, RequiredScopes

    sub = OwnerSub.from_value("auth0|abc123")
    user: AuthUser = {"sub": sub, "email": None, "name": "Dana", "scope": "read:users"}
    must_have = {RequiredScopes.READ_USER_PROFILE}

Notes:
- `RequiredScopes` values must match Auth0-configured scope strings exactly.
"""

from enum import Enum
from typing import TypedDict

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_OWNER_SUB_FORMAT,
    MSG_ERROR_OWNER_SUB_TYPE,
)

__all__ = ["SCOPE_DESCRIPTIONS", "AuthUser", "OwnerSub", "RequiredScopes"]


class OwnerSub(str):
    """
    Auth0 subject (owner) string, e.g., "auth0|abc123".

    This class intentionally subclasses `str` so it behaves like a normal string at
    runtime while adding a constructor helper (`from_value`) to validate inputs in
    one place. Using a nominal type clarifies intent across the codebase.

    Attributes:
        (inherits all behaviors of `str`)

    Notes:
        - Subclassing `str` avoids additional allocations and keeps equality/ordering
          semantics identical to built-in strings.
    """

    # Keep instances as lightweight as a plain string (no per-instance __dict__).
    __slots__ = ()  # SLOT000: subclasses of `str` should define __slots__

    @classmethod
    def from_value(cls, value: str) -> "OwnerSub":
        """
        Validate and construct an `OwnerSub` from a raw string.

        The default validation is minimal and only checks for a pipe `|` separator
        commonly used in Auth0 subject identifiers (e.g., "provider|id"). Tighten
        this check if you want to enforce a stricter format.

        Args:
            value (str): The raw subject string.

        Returns:
            OwnerSub: A validated subject wrapper.

        Raises:
            TypeError: If `value` is not a string.
            ValueError: If `value` does not contain the expected "|" separator.

        Examples:
            >>> OwnerSub.from_value("auth0|abc123")
            'auth0|abc123'
        """
        # Optional: validate format like "provider|id"
        if not isinstance(value, str):
            # EM101/TRY003: assign message first for consistent logging/inspection.
            msg = MSG_ERROR_OWNER_SUB_TYPE
            raise TypeError(msg)
        # Example simple guard; tighten if you want:
        if "|" not in value:
            # EM102/TRY003: use formatted constant for consistency with tests/logs.
            msg = MSG_ERROR_OWNER_SUB_FORMAT.format(value=value)
            raise ValueError(msg)
        return cls(value)


class AuthUser(TypedDict):
    """
    Shape of the authenticated user object passed to route handlers.

    Attributes:
        sub (OwnerSub): Stable subject identifier for the user.
        email (str | None): Email address if present in the token.
        name (str | None): Human-readable name if present in the token.
        scope (str | list[str] | None): Space-delimited string or list of granted scopes.

    Notes:
        - This is intentionally a `TypedDict`, not a Pydantic model, to avoid validation
          overhead in hot paths of the authentication dependency.
    """

    sub: OwnerSub
    email: str | None
    name: str | None
    scope: str | list[str] | None


class RequiredScopes(Enum):
    """
    OAuth scopes enforced by API endpoints.

    Each enum value is the exact scope string assigned by the Auth0 API/application.
    """

    CREATE_OPENAI_CREDENTIALS = "create:openai_credentials"
    READ_USER_PROFILE = "read:user_profile"
    DELETE_USER_ACCOUNT = "delete:user_account"
    SCRAPES_CREATE = "create:scrapes"
    SCRAPES_READ = "read:scrapes"
    SCRAPES_CANCEL = "cancel:scrapes"


# Human-readable descriptions for OAuth scopes. Centralized here so OpenAPI and
# any UI can source consistent text without duplicating strings.
# The dict is keyed by the Enum, not by strings, to keep refactors safer.
SCOPE_DESCRIPTIONS: dict[RequiredScopes, str] = {
    RequiredScopes.READ_USER_PROFILE: "Read user profile",
    RequiredScopes.CREATE_OPENAI_CREDENTIALS: "Manage OpenAI credentials",
    RequiredScopes.SCRAPES_CREATE: "Create scrapes",
    RequiredScopes.SCRAPES_READ: "Read scrapes",
    RequiredScopes.SCRAPES_CANCEL: "Cancel scrapes",
    RequiredScopes.DELETE_USER_ACCOUNT: "Delete user account",
}

# If a new enum value is added but not described here, a fallback will be used
# by OpenAPI generation (see backend/api/openapi.py). Keeping this map close to
# the enum makes it easy to update and test for coverage.
