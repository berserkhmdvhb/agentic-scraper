from pydantic import BaseModel, Field


class UserCredentialsIn(BaseModel):
    """Input schema for saving user's OpenAI credentials."""

    api_key: str = Field(..., description="User's OpenAI API key", example="sk-abc123...")
    project_id: str = Field(..., description="User's OpenAI project ID", example="proj_xyz789")


class UserCredentialsOut(BaseModel):
    """Output schema when returning user's OpenAI credentials."""

    api_key: str = Field(..., example="sk-abc123...")
    project_id: str = Field(..., example="proj_xyz789")


class UserProfile(BaseModel):
    """Represents the authenticated user's profile."""

    sub: str = Field(..., description="User unique identifier", example="auth0|123456789")
    email: str | None = Field(None, description="User email address", example="user@example.com")
    name: str | None = Field(None, description="User full name", example="Alice Smith")

    class Config:
        orm_mode = True
