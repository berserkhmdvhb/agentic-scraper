"""
User-related API routes for authentication, profile, and OpenAI credential management.

This module exposes the following endpoints:
- `GET /me`: Returns the authenticated user's profile.
- `POST /openai-credentials`: Stores the user's OpenAI API key and project ID securely.
- `GET /openai-credentials`: Retrieves previously saved OpenAI credentials for the user.

All routes require authentication via JWT and are protected by scope-based access control
enforced using Auth0-issued scopes and the `check_required_scopes` helper.

Usage:
    Mounted as part of the API under the `/v1/user` prefix or similar.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer

from agentic_scraper.backend.api.auth.dependencies import get_current_user
from agentic_scraper.backend.api.auth.scope_helpers import check_required_scopes
from agentic_scraper.backend.api.models import AuthUser, RequiredScopes
from agentic_scraper.backend.api.schemas.user import (
    UserCredentialsIn,
    UserCredentialsOut,
    UserProfile,
)
from agentic_scraper.backend.api.user_store import load_user_credentials, save_user_credentials
from agentic_scraper.backend.config.messages import (
    MSG_INFO_CREDENTIALS_LOADED,
    MSG_INFO_CREDENTIALS_SAVED,
    MSG_WARNING_NO_CREDENTIALS_FOUND,
)

__all__ = ["get_credentials", "get_me", "post_credentials"]

router = APIRouter()
logger = logging.getLogger(__name__)

CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
auth_scheme = HTTPBearer(auto_error=True)


@router.get("/me", tags=["User"])
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


@router.post("/openai-credentials", status_code=status.HTTP_201_CREATED, tags=["User"])
async def post_credentials(user: CurrentUser, creds: UserCredentialsIn) -> UserCredentialsOut:
    """
    Save the user's OpenAI credentials to persistent storage.

    Args:
        user (AuthUser): The current authenticated user.
        creds (UserCredentialsIn): User's OpenAI API key and project ID.

    Returns:
        UserCredentialsOut: Echoes back the stored credentials.

    Raises:
        HTTPException (400): If the input data is invalid.
        HTTPException (500): On internal storage or validation errors.
    """
    check_required_scopes(user, {RequiredScopes.CREATE_OPENAI_CREDENTIALS})

    try:
        save_user_credentials(
            user_id=user["sub"],
            api_key=creds.api_key,
            project_id=creds.project_id,
        )
        logger.info(MSG_INFO_CREDENTIALS_SAVED.format(user_id=user["sub"]))
        return UserCredentialsOut(api_key=creds.api_key, project_id=creds.project_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid data format for credentials.",
            headers={"X-Error": str(e)},
        ) from e
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error with the database or file storage.",
            headers={"X-Error": str(e)},
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save user credentials due to internal error.",
            headers={"X-Error": str(e)},
        ) from e


@router.get("/openai-credentials", tags=["User"])
async def get_credentials(user: CurrentUser) -> UserCredentialsOut:
    """
    Retrieve the stored OpenAI credentials for the authenticated user.

    Args:
        user (AuthUser): The current authenticated user.

    Returns:
        UserCredentialsOut: Stored OpenAI API key and project ID.

    Raises:
        HTTPException (404): If credentials do not exist.
        HTTPException (500): On parsing or unexpected errors.
    """
    creds = load_user_credentials(user["sub"])

    if not creds:
        logger.warning(MSG_WARNING_NO_CREDENTIALS_FOUND.format(user_id=user["sub"]))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No credentials stored for this user.",
        )

    logger.info(MSG_INFO_CREDENTIALS_LOADED.format(user_id=user["sub"]))
    model_data = creds.model_dump()

    try:
        return UserCredentialsOut.model_validate(model_data)
    except TypeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error while parsing credentials data.",
            headers={"X-Error": str(e)},
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while processing credentials.",
            headers={"X-Error": str(e)},
        ) from e
