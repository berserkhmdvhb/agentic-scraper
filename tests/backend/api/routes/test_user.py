from __future__ import annotations

from typing import Any, Callable

import httpx
import pytest
from fastapi import status

from agentic_scraper.backend.api.schemas.user import (
    UserCredentialsOut,
    UserCredentialsStatus,
    UserProfile,
)

# --------------------------------------------------------------------------- #
# /user/me
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_get_me_ok(
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
) -> None:
    # Include the scope and a couple of profile claims
    token = make_jwt(
        scope="read:user_profile",
        extra_claims={"email": "alice@example.com", "name": "Alice"},
    )
    test_client.headers.update({"Authorization": f"Bearer {token}"})

    res = await test_client.get(f"{api_base}/user/me")
    assert res.status_code == status.HTTP_200_OK, res.text

    prof = UserProfile.model_validate(res.json())
    assert prof.sub.startswith("auth0|")
    assert prof.email == "alice@example.com"
    assert prof.name == "Alice"


@pytest.mark.asyncio
async def test_get_me_missing_scope_forbidden(
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
) -> None:
    # No read:user_profile scope
    token = make_jwt(scope="create:openai_credentials")
    test_client.headers.update({"Authorization": f"Bearer {token}"})

    res = await test_client.get(f"{api_base}/user/me")
    assert res.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}


# --------------------------------------------------------------------------- #
# OpenAI credentials CRUD
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_credentials_status_defaults_false(
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
    user_store_mod: Any,  # ensure temp store path is in-place
    stub_crypto: None,    # ensure stubbed encrypt/decrypt
) -> None:
    token = make_jwt(scope="create:openai_credentials")
    test_client.headers.update({"Authorization": f"Bearer {token}"})

    res = await test_client.get(f"{api_base}/user/openai-credentials/status")
    assert res.status_code == status.HTTP_200_OK, res.text
    status_body = UserCredentialsStatus.model_validate(res.json())
    assert status_body.has_credentials is False


@pytest.mark.asyncio
async def test_credentials_crud_happy_path(
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
    user_store_mod: Any,
    stub_crypto: None,
) -> None:
    token = make_jwt(scope="create:openai_credentials")
    test_client.headers.update({"Authorization": f"Bearer {token}"})

    # PUT (create)
    api_key = "sk-abc123456789"
    project_id = "proj_1"

    put_res = await test_client.put(
        f"{api_base}/user/openai-credentials",
        json={"api_key": api_key, "project_id": project_id},
    )
    assert put_res.status_code == status.HTTP_200_OK, put_res.text
    out_put = UserCredentialsOut.model_validate(put_res.json())
    assert out_put.project_id == project_id
    assert out_put.api_key.endswith(api_key[-4:])
    assert "*" in out_put.api_key

    # GET (masked)
    get_res = await test_client.get(f"{api_base}/user/openai-credentials")
    assert get_res.status_code == status.HTTP_200_OK, get_res.text
    out_get = UserCredentialsOut.model_validate(get_res.json())
    assert out_get.project_id == project_id
    assert out_get.api_key.endswith(api_key[-4:])
    assert "*" in out_get.api_key

    # status -> true
    st_res = await test_client.get(f"{api_base}/user/openai-credentials/status")
    assert st_res.status_code == status.HTTP_200_OK
    st = UserCredentialsStatus.model_validate(st_res.json())
    assert st.has_credentials is True

    # DELETE
    del_res = await test_client.delete(f"{api_base}/user/openai-credentials")
    assert del_res.status_code == status.HTTP_204_NO_CONTENT

    # After delete: GET -> 404; status -> false
    get_res2 = await test_client.get(f"{api_base}/user/openai-credentials")
    assert get_res2.status_code == status.HTTP_404_NOT_FOUND

    st_res2 = await test_client.get(f"{api_base}/user/openai-credentials/status")
    assert st_res2.status_code == status.HTTP_200_OK
    st2 = UserCredentialsStatus.model_validate(st_res2.json())
    assert st2.has_credentials is False


@pytest.mark.asyncio
async def test_get_credentials_404_when_missing(
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
    user_store_mod: Any,
    stub_crypto: None,
) -> None:
    token = make_jwt(scope="create:openai_credentials")
    test_client.headers.update({"Authorization": f"Bearer {token}"})

    res = await test_client.get(f"{api_base}/user/openai-credentials")
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_credentials_404_when_missing(
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
    user_store_mod: Any,
    stub_crypto: None,
) -> None:
    token = make_jwt(scope="create:openai_credentials")
    test_client.headers.update({"Authorization": f"Bearer {token}"})

    res = await test_client.delete(f"{api_base}/user/openai-credentials")
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_put_credentials_value_error_returns_400(
    monkeypatch: pytest.MonkeyPatch,
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
    user_store_mod: Any,
    stub_crypto: None,
) -> None:
    # Force save_user_credentials to raise ValueError so we hit the 400 branch.
    import agentic_scraper.backend.api.routes.user as user_routes

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise ValueError("bad creds")

    monkeypatch.setattr(user_routes, "save_user_credentials", _boom, raising=True)

    token = make_jwt(scope="create:openai_credentials")
    test_client.headers.update({"Authorization": f"Bearer {token}"})

    res = await test_client.put(
        f"{api_base}/user/openai-credentials",
        json={"api_key": "sk-xyz", "project_id": "p1"},
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_put_credentials_oserror_returns_500(
    monkeypatch: pytest.MonkeyPatch,
    test_client: httpx.AsyncClient,
    make_jwt: Callable[..., str],
    jwks_mock: None,
    api_base: str,
    user_store_mod: Any,
    stub_crypto: None,
) -> None:
    import agentic_scraper.backend.api.routes.user as user_routes

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(user_routes, "save_user_credentials", _boom, raising=True)

    token = make_jwt(scope="create:openai_credentials")
    test_client.headers.update({"Authorization": f"Bearer {token}"})

    res = await test_client.put(
        f"{api_base}/user/openai-credentials",
        json={"api_key": "sk-xyz", "project_id": "p1"},
    )
    assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
