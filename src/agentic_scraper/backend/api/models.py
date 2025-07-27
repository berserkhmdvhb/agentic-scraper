from typing import TypedDict


class AuthUser(TypedDict):
    sub: str
    email: str | None
    name: str | None
