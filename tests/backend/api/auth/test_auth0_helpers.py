from __future__ import annotations

from typing import Any, Callable

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi import HTTPException, status

from agentic_scraper.backend.core import settings as settings_module


@pytest.mark.asyncio
async def test_verify_jwt_success(
    jwks_mock: None,
    make_jwt: Callable[..., str],
    settings: settings_module.Settings,
) -> None:
    # Import after fixtures; then align module-level settings with fixture.
    from agentic_scraper.backend.api.auth import auth0_helpers as ah

    ah.settings = settings  # ensure issuer/audience/algorithms match the minted token

    token: str = make_jwt(scope="read:user_profile")
    payload = await ah.verify_jwt(token)

    assert isinstance(payload, dict)
    assert payload["iss"] == settings.auth0_issuer
    assert payload["aud"] == settings.auth0_api_audience
    assert payload["sub"].startswith("auth0|")
    assert "read:user_profile" in str(payload.get("scope", ""))


@pytest.mark.asyncio
async def test_verify_jwt_expired_raises_http_401(
    jwks_mock: None,
    make_jwt: Callable[..., str],
    settings: settings_module.Settings,
) -> None:
    from agentic_scraper.backend.api.auth import auth0_helpers as ah

    ah.settings = settings

    token: str = make_jwt(expires_in=-5)
    with pytest.raises(HTTPException) as exc:
        await ah.verify_jwt(token)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_verify_jwt_wrong_audience_raises_http_401(
    jwks_mock: None,
    make_jwt: Callable[..., str],
    settings: settings_module.Settings,
) -> None:
    from agentic_scraper.backend.api.auth import auth0_helpers as ah

    ah.settings = settings

    token: str = make_jwt(extra_claims={"aud": "https://wrong.example.com"})
    with pytest.raises(HTTPException) as exc:
        await ah.verify_jwt(token)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_verify_jwt_no_matching_kid_raises_http_401(
    jwks_mock: None,
    make_jwt: Callable[..., str],
    monkeypatch: MonkeyPatch,
    settings: settings_module.Settings,
) -> None:
    from agentic_scraper.backend.api.auth import auth0_helpers as ah

    ah.settings = settings

    async def _empty_jwks() -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr(ah.jwks_cache_instance, "get_jwks", _empty_jwks, raising=True)

    token: str = make_jwt()
    with pytest.raises(HTTPException) as exc:
        await ah.verify_jwt(token)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_verify_jwt_empty_token_raises_http_401(
    settings: settings_module.Settings,
) -> None:
    from agentic_scraper.backend.api.auth import auth0_helpers as ah

    ah.settings = settings

    with pytest.raises(HTTPException) as exc:
        await ah.verify_jwt("  ")

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
