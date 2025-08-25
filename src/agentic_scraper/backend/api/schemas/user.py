from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from agentic_scraper.backend.config.messages import MSG_ERROR_EMPTY_STRING
from agentic_scraper.backend.utils.validators import validate_optional_str


class UserCredentialsIn(BaseModel):
    """
    Input schema for saving a user's OpenAI credentials.

    - `api_key` is accepted as a SecretStr and will not be logged.
    - `project_id` is trimmed and must be non-empty.
    """

    model_config = ConfigDict(extra="ignore")

    api_key: SecretStr = Field(
        ...,
        description="User's OpenAI API key (stored securely, not shown in logs).",
        json_schema_extra={"example": "sk-abc123..."},
    )
    project_id: str = Field(
        ...,
        min_length=1,
        description="User's OpenAI project ID.",
        json_schema_extra={"example": "proj_xyz789"},
    )

    @field_validator("project_id", mode="before")
    @classmethod
    def _strip_project_id(cls, v: str) -> str:
        v = v.strip() if isinstance(v, str) else v
        if not isinstance(v, str) or not v:
            # keep message simple; deeper validation handled in store validators if needed
            raise ValueError(MSG_ERROR_EMPTY_STRING.format(field="project_id"))
        return v


class UserCredentialsOut(BaseModel):
    """
    Output schema for returning the user's OpenAI credentials.

    - `api_key` is a masked string (e.g., only last 4 chars visible).
    """

    model_config = ConfigDict(extra="ignore")

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

    model_config = ConfigDict(extra="ignore")

    has_credentials: bool = Field(
        ...,
        description="Whether the user has saved OpenAI credentials.",
        json_schema_extra={"example": True},
    )


class UserProfile(BaseModel):
    """Represents the authenticated user's profile."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    sub: str = Field(
        ...,
        description="User unique identifier (subject).",
        json_schema_extra={"example": "auth0|123456789"},
    )
    email: EmailStr | None = Field(
        None,
        description="User email address.",
        json_schema_extra={"example": "user@example.com"},
    )
    name: str | None = Field(
        None,
        description="User full name.",
        json_schema_extra={"example": "Alice Smith"},
    )

    @field_validator("sub", mode="before")
    @classmethod
    def _clean_sub(cls, v: str) -> str:
        s = v.strip() if isinstance(v, str) else v
        if not isinstance(s, str) or not s:
            raise ValueError(MSG_ERROR_EMPTY_STRING.format(field="sub"))
        return s

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            return v  # let Pydantic handle the type error
        # Trim, then reuse central validator to reject empty-after-trim
        trimmed = v.strip()
        return validate_optional_str(trimmed, "name")
