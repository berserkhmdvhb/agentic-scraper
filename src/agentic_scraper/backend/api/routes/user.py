"""
User-related API routes for authentication, profile, and OpenAI credential management.

Endpoints / Dependencies:
- `GET /user/me` (`get_me`): Return the current user's profile (requires `read:user_profile`).
- `GET /user/openai-credentials` (`get_credentials`): Return masked OpenAI credentials.
- `PUT /user/openai-credentials` (`put_credentials`): Create or update OpenAI credentials.
- `DELETE /user/openai-credentials` (`delete_credentials`): Delete stored credentials.
- `GET /user/openai-credentials/status` (`credentials_status`): Presence check for credentials.

Auth:
- All endpoints require a valid Auth0-issued JWT via the dependency `get_current_user`.
- Scope enforcement is performed with `check_required_scopes` per endpoint.

Response Models:
- `UserProfile`, `UserCredentialsOut`, `UserCredentialsStatus`.

Error Codes & Status:
- 400: Invalid input when saving credentials.
- 401/403: Authentication or scope failures (raised by auth dependencies).
- 404: Credentials not found (GET/DELETE).
- 500: I/O or unexpected internal failures during load/save/delete.

Usage:
    from fastapi import FastAPI
    from agentic_scraper.backend.api.routes.user import router
    app = FastAPI()
    app.include_router(router)

Notes:
- Secrets are never returned in cleartext; API keys are masked before returning.
- 204 DELETE response intentionally has no body (`response_model=None`).
"""

from __future__ import annotations

import logging
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import SecretStr

from agentic_scraper.backend.api.auth.dependencies import get_current_user
from agentic_scraper.backend.api.auth.scope_helpers import check_required_scopes
from agentic_scraper.backend.api.models import AuthUser, RequiredScopes
from agentic_scraper.backend.api.schemas.user import (
    UserCredentialsIn,
    UserCredentialsOut,
    UserCredentialsStatus,
    UserProfile,
)
from agentic_scraper.backend.api.stores.user_store import (
    delete_user_credentials,
    has_user_credentials,
    load_user_credentials,
    save_user_credentials,
)
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_CREDENTIALS_DELETE_FAILED,
    MSG_ERROR_CREDENTIALS_SAVE_INTERNAL,
    MSG_ERROR_CREDENTIALS_STORAGE,
    MSG_ERROR_INVALID_CREDENTIALS_FORMAT,
    MSG_ERROR_NO_CREDENTIALS_FOR_USER,
    MSG_ERROR_NO_CREDENTIALS_TO_DELETE,
    MSG_ERROR_PARSING_CREDENTIALS,
    MSG_ERROR_UNEXPECTED_CREDENTIALS,
    MSG_INFO_CREDENTIALS_LOADED,
    MSG_INFO_CREDENTIALS_SAVED,
    MSG_WARNING_NO_CREDENTIALS_FOUND,
)

__all__ = [
    "credentials_status",
    "delete_credentials",
    "get_credentials",
    "get_me",
    "put_credentials",
    "router",
]

router = APIRouter(prefix="/user", tags=["User"])
logger = logging.getLogger(__name__)

# FastAPI dependency alias for brevity/clarity in handlers.
CurrentUser = Annotated[AuthUser, Depends(get_current_user)]


def _mask_secret(value: str | SecretStr | None, show_last: int = 4) -> str:
    """
    Mask a secret for safe return in API responses.

    The function returns a string of asterisks with only the last `show_last`
    characters of the secret visible. If the input is a `SecretStr`, it is
    unwrapped first; `None` returns an empty string.

    Args:
        value (str | SecretStr | None): The sensitive value to mask.
        show_last (int): Number of trailing characters to reveal (default: 4).

    Returns:
        str: Masked representation suitable for API responses.

    Examples:
        >>> _mask_secret("sk-abcdef", show_last=4)
        '***cdef'
        >>> _mask_secret(SecretStr("sk-abcdef"), show_last=2)
        '******ef'
        >>> _mask_secret(None)
        ''
    """
    if value is None:
        return ""
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    if len(value) <= show_last:
        return "*" * len(value)
    return "*" * (len(value) - show_last) + value[-show_last:]


@router.get("/me", response_model=UserProfile)
async def get_me(user: CurrentUser) -> UserProfile:
    """
    Retrieve the current user's profile.

    Requires:
        `read:user_profile` scope.

    Args:
        user (AuthUser): Injected by `get_current_user` after JWT verification.

    Returns:
        UserProfile: The authenticated user's profile DTO.
    """
    # Enforce scope at the route boundary to fail fast before any work.
    check_required_scopes(user, {RequiredScopes.READ_USER_PROFILE})
    return UserProfile(
        sub=user["sub"],
        email=user.get("email"),
        name=user.get("name"),
    )


@router.get("/openai-credentials", response_model=UserCredentialsOut)
async def get_credentials(user: CurrentUser) -> UserCredentialsOut:
    """
    Retrieve stored (masked) OpenAI credentials.

    Requires:
        `create:openai_credentials` scope.

    Args:
        user (AuthUser): Injected auth context.

    Returns:
        UserCredentialsOut: Masked API key and project id.

    Raises:
        HTTPException: 404 if no credentials stored for the user.
        HTTPException: 500 on parsing/unexpected errors.
    """
    check_required_scopes(user, {RequiredScopes.CREATE_OPENAI_CREDENTIALS})

    creds = load_user_credentials(user["sub"])
    if not creds:
        logger.warning(MSG_WARNING_NO_CREDENTIALS_FOUND.format(user_id=str(user["sub"])))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_ERROR_NO_CREDENTIALS_FOR_USER,
        )

    logger.info(MSG_INFO_CREDENTIALS_LOADED.format(user_id=user["sub"]))
    model_data = creds.model_dump()  # keys: 'api_key', 'project_id'
    try:
        return UserCredentialsOut(
            api_key=_mask_secret(model_data.get("api_key")),
            project_id=model_data.get("project_id", ""),
        )
    except TypeError as e:
        # Defensive: ensure unexpected shapes don't leak internals to clients.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MSG_ERROR_PARSING_CREDENTIALS,
        ) from e
    except Exception as e:  # pragma: no cover (defensive)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MSG_ERROR_UNEXPECTED_CREDENTIALS,
        ) from e


@router.put(
    "/openai-credentials", status_code=status.HTTP_200_OK, response_model=UserCredentialsOut
)
async def put_credentials(user: CurrentUser, creds: UserCredentialsIn) -> UserCredentialsOut:
    """
    Create or update OpenAI credentials.

    Requires:
        `create:openai_credentials` scope.

    Args:
        user (AuthUser): Injected auth context.
        creds (UserCredentialsIn): Incoming credentials payload.

    Returns:
        UserCredentialsOut: Masked API key and project id.

    Raises:
        HTTPException: 400 on validation errors (bad formats).
        HTTPException: 500 on storage or unexpected errors.
    """
    check_required_scopes(user, {RequiredScopes.CREATE_OPENAI_CREDENTIALS})

    try:
        save_user_credentials(
            user_id=user["sub"],
            api_key=creds.api_key.get_secret_value(),
            project_id=creds.project_id,
        )
        logger.info(MSG_INFO_CREDENTIALS_SAVED.format(user_id=user["sub"]))
        # Echo masked values back to caller for immediate confirmation.
        return UserCredentialsOut(
            api_key=_mask_secret(creds.api_key),
            project_id=creds.project_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MSG_ERROR_INVALID_CREDENTIALS_FORMAT,
        ) from e
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MSG_ERROR_CREDENTIALS_STORAGE,
        ) from e
    except Exception as e:  # pragma: no cover (defensive)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MSG_ERROR_CREDENTIALS_SAVE_INTERNAL,
        ) from e


@router.delete(
    "/openai-credentials",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,  # 204 must not have a body
)
async def delete_credentials(user: CurrentUser) -> None:
    """
    Delete stored OpenAI credentials.

    Requires:
        `create:openai_credentials` scope.

    Args:
        user (AuthUser): Injected auth context.

    Returns:
        None: Always returns HTTP 204 on success.

    Raises:
        HTTPException: 404 if credentials do not exist.
        HTTPException: 500 on unexpected delete failures.
    """
    check_required_scopes(user, {RequiredScopes.CREATE_OPENAI_CREDENTIALS})

    def _raise_not_found() -> NoReturn:
        """Local helper to raise a consistent 404 for missing credentials."""
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_ERROR_NO_CREDENTIALS_TO_DELETE,
        )

    try:
        success = delete_user_credentials(user["sub"])
        if not success:
            _raise_not_found()
    except HTTPException:
        # Re-raise the explicit 404 above.
        raise
    except Exception as e:  # pragma: no cover (defensive)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MSG_ERROR_CREDENTIALS_DELETE_FAILED,
        ) from e


@router.get("/openai-credentials/status", response_model=UserCredentialsStatus)
async def credentials_status(user: CurrentUser) -> UserCredentialsStatus:
    """
    Return whether OpenAI credentials exist for the current user.

    Requires:
        `create:openai_credentials` scope.

    Args:
        user (AuthUser): Injected auth context.

    Returns:
        UserCredentialsStatus: Presence flag for stored credentials.
    """
    check_required_scopes(user, {RequiredScopes.CREATE_OPENAI_CREDENTIALS})
    # Fast path: returns a small DTO indicating presence without exposing secrets.
    return UserCredentialsStatus(has_credentials=has_user_credentials(user["sub"]))
