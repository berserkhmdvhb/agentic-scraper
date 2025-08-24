from __future__ import annotations

from typing import Set

import pytest
from fastapi import HTTPException, status

from agentic_scraper.backend.api.auth.scope_helpers import check_required_scopes
from agentic_scraper.backend.api.models import AuthUser, OwnerSub, RequiredScopes


def make_user(scope: str | list[str] | None) -> AuthUser:
    return {
        "sub": OwnerSub("auth0|user123"),
        "email": "user@example.com",
        "name": "User",
        "scope": scope,
    }


def test_check_required_scopes_success_with_string_scope() -> None:
    payload = make_user("read:user_profile write:jobs")
    required: Set[RequiredScopes] = {RequiredScopes.READ_USER_PROFILE}
    check_required_scopes(payload, required)


def test_check_required_scopes_success_with_list_scope() -> None:
    payload = make_user(["read:user_profile", "write:jobs"])
    required: Set[RequiredScopes] = {RequiredScopes.READ_USER_PROFILE}
    check_required_scopes(payload, required)


def test_check_required_scopes_missing_raises_forbidden() -> None:
    payload = make_user("read:something_else")
    required: Set[RequiredScopes] = {RequiredScopes.READ_USER_PROFILE}
    with pytest.raises(HTTPException) as exc:
        check_required_scopes(payload, required)
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


def test_check_required_scopes_none_scope_raises_forbidden() -> None:
    payload = make_user(None)
    required: Set[RequiredScopes] = {RequiredScopes.READ_USER_PROFILE}
    with pytest.raises(HTTPException) as exc:
        check_required_scopes(payload, required)
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
