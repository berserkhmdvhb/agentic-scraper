"""
User-related API routes for authentication, profile, and OpenAI credential management.

This module exposes the following endpoints:
- `GET /me`:
    Returns the authenticated user's profile.
- `GET /openai-credentials`:
    Retrieves previously saved (masked) OpenAI credentials for the user.
- `PUT /openai-credentials`:
    Creates or updates the user's OpenAI API key and project ID (response masked).
- `DELETE /openai-credentials`:
    Deletes the stored OpenAI credentials for the user.
- `GET /openai-credentials/status`:
    Returns whether the user has stored credentials.

All routes require authentication via JWT and are protected by scope-based access control
enforced using Auth0-issued scopes and the `check_required_scopes` helper.

Usage:
    Mounted as part of the API under the `/v1/user` prefix or similar.
"""

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

router = APIRouter()
logger = logging.getLogger(__name__)

CurrentUser = Annotated[AuthUser, Depends(get_current_user)]


def _mask_secret(value: str | SecretStr | None, show_last: int = 4) -> str | None:
    if value is None:
        return None
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    if len(value) <= show_last:
        return "*" * len(value)
    return "*" * (len(value) - show_last) + value[-show_last:]


router.get("/openai-credentials", tags=["User"])


async def get_me(user: CurrentUser) -> UserProfile:
    """
    Retrieve the current user's profile.

    Requires the `read:user_profile` scope and returns a subset of user data from the JWT.

    Args:
        user (AuthUser): The current authenticated user extracted from the JWT.

    Returns:
        UserProfile: Object containing `sub`, `email`, and `name`.

    Raises:
        HTTPException (403): If required scopes are missing.
    """
    check_required_scopes(user, {RequiredScopes.READ_USER_PROFILE})

    return UserProfile(
        sub=user["sub"],
        email=user.get("email"),
        name=user.get("name"),
    )


@router.get("/openai-credentials", tags=["User"])
async def get_credentials(user: CurrentUser) -> UserCredentialsOut:
    """
    Retrieve the stored OpenAI credentials for the authenticated user.
    Requires the `create:openai_credentials` scope.

    Args:
        user (AuthUser): The current authenticated user.

    Returns:
        UserCredentialsOut: Masked OpenAI API key and the stored project ID.

    Raises:
        HTTPException (404): If credentials do not exist.
        HTTPException (500): On parsing or unexpected errors.
    """
    check_required_scopes(user, {RequiredScopes.CREATE_OPENAI_CREDENTIALS})

    creds = load_user_credentials(user["sub"])
    if not creds:
        logger.warning(MSG_WARNING_NO_CREDENTIALS_FOUND.format(user_id=user["sub"]))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_ERROR_NO_CREDENTIALS_FOR_USER,
        )

    logger.info(MSG_INFO_CREDENTIALS_LOADED.format(user_id=user["sub"]))
    model_data = creds.model_dump()

    try:
        # Always mask sensitive values in responses
        return UserCredentialsOut(
            api_key=_mask_secret(model_data.get("api_key")),
            project_id=model_data.get("project_id"),
        )
    except TypeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MSG_ERROR_PARSING_CREDENTIALS,
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MSG_ERROR_UNEXPECTED_CREDENTIALS,
        ) from e


@router.put(
    "/openai-credentials",
    status_code=status.HTTP_200_OK,
    tags=["User"],
)
async def put_credentials(user: CurrentUser, creds: UserCredentialsIn) -> UserCredentialsOut:
    """
    Create or update the user's OpenAI credentials in persistent storage.
    Requires the `create:openai_credentials` scope.

    Args:
        user (AuthUser): The current authenticated user.
        creds (UserCredentialsIn): User's OpenAI API key and project ID.

    Returns:
        UserCredentialsOut: Masked API key and the stored project ID.

    Raises:
        HTTPException (400): If the input data is invalid.
        HTTPException (500): On internal storage or validation errors.
    """
    check_required_scopes(user, {RequiredScopes.CREATE_OPENAI_CREDENTIALS})

    try:
        save_user_credentials(
            user_id=user["sub"],
            api_key=creds.api_key.get_secret_value(),
            project_id=creds.project_id,
        )
        logger.info(MSG_INFO_CREDENTIALS_SAVED.format(user_id=user["sub"]))
        # Return masked values to avoid echoing secrets
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MSG_ERROR_CREDENTIALS_SAVE_INTERNAL,
        ) from e


@router.delete("/openai-credentials", status_code=status.HTTP_204_NO_CONTENT, tags=["User"])
async def delete_credentials(user: CurrentUser) -> None:
    """
    Delete the stored OpenAI credentials for the authenticated user.
    Requires the `create:openai_credentials` scope.

    Raises:
        HTTPException (404): If no credentials exist.
        HTTPException (500): On internal deletion errors.
    """
    check_required_scopes(user, {RequiredScopes.CREATE_OPENAI_CREDENTIALS})

    def raise_not_found() -> NoReturn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_ERROR_NO_CREDENTIALS_TO_DELETE,
        )

    try:
        success = delete_user_credentials(user["sub"])
        if not success:
            raise_not_found()
    except HTTPException:
        # Re-raise 404 from raise_not_found
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MSG_ERROR_CREDENTIALS_DELETE_FAILED,
        ) from e


@router.get("/openai-credentials/status", response_model=UserCredentialsStatus, tags=["User"])
async def credentials_status(user: CurrentUser) -> dict[str, bool]:
    """
    Check if the user has stored OpenAI credentials.
    Requires the `create:openai_credentials` scope.

    Args:
        user (AuthUser): The current authenticated user.

    Returns:
        dict[str, bool]: {"has_credentials": true} or {"has_credentials": false}
    """
    check_required_scopes(user, {RequiredScopes.CREATE_OPENAI_CREDENTIALS})
    return {"has_credentials": has_user_credentials(user["sub"])}
