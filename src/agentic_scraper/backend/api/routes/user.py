"""
User-related API routes for authentication, profile, and OpenAI credential management.

Exposed endpoints:
- GET    /me
- GET    /openai-credentials
- PUT    /openai-credentials
- DELETE /openai-credentials
- GET    /openai-credentials/status
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
]

router = APIRouter(prefix="/user", tags=["User"])
logger = logging.getLogger(__name__)

CurrentUser = Annotated[AuthUser, Depends(get_current_user)]


def _mask_secret(value: str | SecretStr | None, show_last: int = 4) -> str:
    """
    Mask a secret for safe return in API responses.
    Always returns a string (empty string if None).
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
    Retrieve the current user's profile (requires read:user_profile).
    """
    check_required_scopes(user, {RequiredScopes.READ_USER_PROFILE})
    return UserProfile(
        sub=user["sub"],
        email=user.get("email"),
        name=user.get("name"),
    )


@router.get("/openai-credentials", response_model=UserCredentialsOut)
async def get_credentials(user: CurrentUser) -> UserCredentialsOut:
    """
    Retrieve stored (masked) OpenAI credentials (requires create:openai_credentials).
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
    Create or update OpenAI credentials (requires create:openai_credentials).
    """
    check_required_scopes(user, {RequiredScopes.CREATE_OPENAI_CREDENTIALS})

    try:
        save_user_credentials(
            user_id=user["sub"],
            api_key=creds.api_key.get_secret_value(),
            project_id=creds.project_id,
        )
        logger.info(MSG_INFO_CREDENTIALS_SAVED.format(user_id=user["sub"]))
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
    Delete stored OpenAI credentials (requires create:openai_credentials).
    """
    check_required_scopes(user, {RequiredScopes.CREATE_OPENAI_CREDENTIALS})

    def _raise_not_found() -> NoReturn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_ERROR_NO_CREDENTIALS_TO_DELETE,
        )

    try:
        success = delete_user_credentials(user["sub"])
        if not success:
            _raise_not_found()
    except HTTPException:
        # re-raise the explicit 404 above
        raise
    except Exception as e:  # pragma: no cover (defensive)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MSG_ERROR_CREDENTIALS_DELETE_FAILED,
        ) from e


@router.get("/openai-credentials/status", response_model=UserCredentialsStatus)
async def credentials_status(user: CurrentUser) -> UserCredentialsStatus:
    """
    Return whether credentials exist (requires create:openai_credentials).
    """
    check_required_scopes(user, {RequiredScopes.CREATE_OPENAI_CREDENTIALS})
    return UserCredentialsStatus(has_credentials=has_user_credentials(user["sub"]))
