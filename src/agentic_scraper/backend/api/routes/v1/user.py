import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agentic_scraper.backend.api.auth.dependencies import get_current_user
from agentic_scraper.backend.api.auth.scope_helpers import check_required_scopes
from agentic_scraper.backend.api.models import AuthUser, RequiredScopes
from agentic_scraper.backend.api.schemas.user import (
    UserCredentialsIn,
    UserCredentialsOut,
    UserProfile,
)
from agentic_scraper.backend.api.user_store import load_user_credentials, save_user_credentials
from agentic_scraper.backend.config.messages import MSG_WARNING_NO_CREDENTIALS_FOUND

router = APIRouter()
logger = logging.getLogger(__name__)

CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
auth_scheme = HTTPBearer(auto_error=True)

# Versioned route
@router.get("/me", tags=["User"])
async def get_me(
    user: CurrentUser,
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> UserProfile:
    """
    Retrieve the current user's profile, using /userinfo fallback if name/email is missing.
    """
    check_required_scopes(user, {RequiredScopes.READ_USER_PROFILE})
    
    return UserProfile(
        sub=user["sub"],
        email=user.get("email"),
        name=user.get("name"),
    )


@router.post("/openai-credentials", status_code=status.HTTP_201_CREATED, tags=["User"])
async def post_credentials(
    user: CurrentUser,
    creds: UserCredentialsIn,
) -> UserCredentialsOut:
    """
    Save the user's OpenAI credentials.

    This endpoint stores the provided API key and project ID for the user,
    creating new credentials if none exist.

    Args:
        creds (UserCredentialsIn): The user's OpenAI credentials (API key and project ID).
        user (CurrentUser): The current authenticated user, injected via the `Depends` dependency.

    Returns:
        UserCredentialsOut: The saved credentials (API key and project ID).

    Raises:
        HTTPException: If there is an error with the data format, database, or any unforeseen error.
    """
    # Define the required scope for this route as a set
    required_scopes = {RequiredScopes.CREATE_OPENAI_CREDENTIALS}

    # Ensure the user has the required scope
    check_required_scopes(user, required_scopes)

    try:
        # Try to save user credentials
        save_user_credentials(
            user_id=user["sub"],
            api_key=creds.api_key,
            project_id=creds.project_id,
        )
        # Return created credentials with 201 Created status
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
    Retrieve the user's saved OpenAI credentials.

    This endpoint fetches the stored API key and project ID for the user.
    If no credentials are found, a 404 error is raised.

    Args:
        user (CurrentUser): The current authenticated user, injected via the `Depends` dependency.

    Returns:
        UserCredentialsOut: The stored OpenAI credentials (API key and project ID).

    Raises:
        HTTPException: If no credentials are found, or if there is an error during data parsing.
    """
    creds = load_user_credentials(user["sub"])

    # If no credentials are found, raise 404
    if not creds:
        logger.warning(MSG_WARNING_NO_CREDENTIALS_FOUND.format(user_id=user["sub"]))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No credentials stored for this user."
        )

    model_data = creds.model_dump()

    try:
        # Validate and parse the data into the UserCredentialsOut model
        user_credentials = UserCredentialsOut.model_validate(model_data)
    except TypeError as e:  # Catch TypeError for issues with data conversion
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error while parsing credentials data.",
            headers={"X-Error": str(e)},  # Include the original exception for traceability
        ) from e
    except Exception as e:  # Catch any unforeseen errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while processing credentials.",
            headers={"X-Error": str(e)},  # Raise the original exception for debugging
        ) from e

    return user_credentials
