from pydantic import BaseModel, Field


class UserCredentialsIn(BaseModel):
    """Input schema for saving user's OpenAI credentials."""

    api_key: str = Field(
        ..., description="User's OpenAI API key", json_schema_extra={"example": "sk-abc123..."}
    )
    project_id: str = Field(
        ..., description="User's OpenAI project ID", json_schema_extra={"example": "proj_xyz789"}
    )


class UserCredentialsOut(BaseModel):
    """Output schema when returning user's OpenAI credentials."""

    api_key: str = Field(..., json_schema_extra={"example": "sk-abc123..."})
    project_id: str = Field(..., json_schema_extra={"example": "proj_xyz789"})


class UserProfile(BaseModel):
    """Represents the authenticated user's profile."""

    sub: str = Field(
        ..., description="User unique identifier", json_schema_extra={"example": "auth0|123456789"}
    )
    email: str | None = Field(
        None, description="User email address", json_schema_extra={"example": "user@example.com"}
    )
    name: str | None = Field(
        None, description="User full name", json_schema_extra={"example": "Alice Smith"}
    )

    class Config:
        orm_mode = True
