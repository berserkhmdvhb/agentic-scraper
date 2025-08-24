from pydantic import BaseModel, ConfigDict, Field, SecretStr


class UserCredentialsIn(BaseModel):
    """Input schema for saving user's OpenAI credentials."""

    api_key: SecretStr = Field(
        ...,
        description="User's OpenAI API key (stored securely, not shown in logs).",
        json_schema_extra={"example": "sk-abc123..."},
    )
    project_id: str = Field(
        ..., description="User's OpenAI project ID", json_schema_extra={"example": "proj_xyz789"}
    )


class UserCredentialsOut(BaseModel):
    """Output schema when returning user's OpenAI credentials (masked key)."""

    api_key: str = Field(
        ...,
        description="Masked OpenAI API key (only last 4 chars visible).",
        json_schema_extra={"example": "sk-********************************cdef"},
    )
    project_id: str = Field(
        ...,
        description="OpenAI project ID.",
        json_schema_extra={"example": "proj_xyz789"},
    )


class UserCredentialsStatus(BaseModel):
    """Presence info for stored credentials."""

    has_credentials: bool = Field(..., description="Whether the user has saved OpenAI credentials.")


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

    model_config = ConfigDict(from_attributes=True)
