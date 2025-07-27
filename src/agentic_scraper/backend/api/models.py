from enum import Enum
from typing import TypedDict


class AuthUser(TypedDict):
    sub: str
    email: str | None
    name: str | None
    scope: str


class RequiredScopes(Enum):
    CREATE_OPENAI_CREDENTIALS = "create:openai_credentials"
    READ_USER_PROFILE = "read:user_profile"
    DELETE_USER_ACCOUNT = "delete:user_account"

