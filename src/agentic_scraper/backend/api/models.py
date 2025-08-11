from enum import Enum
from typing import TypedDict

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_OWNER_SUB_FORMAT,
    MSG_ERROR_OWNER_SUB_TYPE,
)

__all__ = ["AuthUser", "OwnerSub", "RequiredScopes"]


class OwnerSub(str):
    """Auth0 subject (owner) string, e.g. 'auth0|abc123'."""

    __slots__ = ()  # SLOT000: subclasses of `str` should define __slots__

    @classmethod
    def from_value(cls, value: str) -> "OwnerSub":
        # optional: validate format like "provider|id"
        if not isinstance(value, str):
            msg = MSG_ERROR_OWNER_SUB_TYPE  # EM101/TRY003: assign message first
            raise TypeError(msg)
        # Example simple guard; tighten if you want:
        if "|" not in value:
            msg = MSG_ERROR_OWNER_SUB_FORMAT.format(value=value)  # EM102/TRY003
            raise ValueError(msg)
        return cls(value)


class AuthUser(TypedDict):
    sub: OwnerSub
    email: str | None
    name: str | None
    scope: str


class RequiredScopes(Enum):
    CREATE_OPENAI_CREDENTIALS = "create:openai_credentials"
    READ_USER_PROFILE = "read:user_profile"
    DELETE_USER_ACCOUNT = "delete:user_account"
    SCRAPES_CREATE = "create:scrapes"
    SCRAPES_READ = "read:scrapes"
    SCRAPES_CANCEL = "cancel:scrapes"
