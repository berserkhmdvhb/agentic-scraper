from __future__ import annotations

from typing import Callable

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from agentic_scraper.backend.api.auth import dependencies as deps
from agentic_scraper.backend.core import settings as settings_module


@pytest.mark.asyncio
async def test_get_current_user_success(
    jwks_mock: None,
    make_jwt: Callable[..., str],
    settings: settings_module.Settings,
    monkeypatch: MonkeyPatch,
) -> None:
    # Ensure auth0_helpers uses the same settings as the minted token
    from agentic_scraper.backend.api.auth import auth0_helpers as ah

    ah.settings = settings

    token: str = make_jwt(scope="read:user_profile")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await deps.get_current_user(creds)

    assert user["sub"].startswith("auth0|")
    assert user["email"] is None or isinstance(user["email"], str)
    assert user["name"] is None or isinstance(user["name"], str)
    # scope may be string, list, or None; success path doesn't assert specific form


@pytest.mark.asyncio
async def test_get_current_user_missing_sub_raises_401(
    jwks_mock: None,
    make_jwt: Callable[..., str],
    settings: settings_module.Settings,
    monkeypatch: MonkeyPatch,
) -> None:
    from agentic_scraper.backend.api.auth import auth0_helpers as ah

    ah.settings = settings

    token: str = make_jwt(extra_claims={"sub": None})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(creds)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_current_user_propagates_401_from_verify(
    monkeypatch: MonkeyPatch,
) -> None:
    # Patch verify_jwt imported in dependencies to raise HTTP 401
    async def _fake_verify(_token: str) -> dict[str, str]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad token")

    monkeypatch.setattr(deps, "verify_jwt", _fake_verify, raising=True)

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="whatever")
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(creds)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
