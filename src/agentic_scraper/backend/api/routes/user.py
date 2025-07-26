from typing import Annotated, TypedDict

from fastapi import APIRouter, Depends, HTTPException, Response, status

from agentic_scraper.backend.api.auth.dependencies import get_current_user
from agentic_scraper.backend.api.schemas.user import (
    UserCredentialsIn,
    UserCredentialsOut,
    UserProfile,
)
from agentic_scraper.backend.api.user_store import load_user_credentials, save_user_credentials

router = APIRouter()


class AuthUser(TypedDict):
    sub: str
    email: str | None
    name: str | None


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]


@router.get("/me", tags=["User"])
def get_me(user: CurrentUser) -> UserProfile:
    return UserProfile(
        sub=user["sub"],
        email=user.get("email"),
        name=user.get("name"),
    )


@router.post("/openai-credentials", status_code=status.HTTP_204_NO_CONTENT, tags=["User"])
def post_credentials(
    creds: UserCredentialsIn,
    user: CurrentUser,
) -> Response:
    save_user_credentials(
        user_id=user["sub"],
        api_key=creds.api_key,
        project_id=creds.project_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/openai-credentials", tags=["User"])
def get_credentials(user: CurrentUser) -> UserCredentialsOut:
    creds = load_user_credentials(user["sub"])
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No credentials stored for this user."
        )
    return UserCredentialsOut(**creds)
