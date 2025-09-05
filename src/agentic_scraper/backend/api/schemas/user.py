"""
API schemas for user authentication and OpenAI credential management.

Models:
- `UserCredentialsIn`: Input DTO for saving a user's OpenAI credentials.
- `UserCredentialsOut`: Output DTO with masked API key and project ID.
- `UserCredentialsStatus`: Presence indicator for stored credentials.
- `UserProfile`: Authenticated user's profile.

Serialization:
- Empty strings for optional fields are normalized to `None` (where applicable).
- API keys are handled as `SecretStr` on input; outputs are masked strings.
- `UserProfile` accepts attribute-based construction (`from_attributes=True`).

Validation & Defaults:
- `project_id` and `sub` are trimmed and rejected if empty.
- Optional name strings are normalized via `validate_optional_str`.

Usage:
    from agentic_scraper.backend.api.schemas.user import UserCredentialsIn

    creds = UserCredentialsIn(api_key="sk-abc...", project_id="proj_123")
    payload = creds.model_dump()

Notes:
- These models shape API payloads; they do not perform I/O or persistence.
- Keep masking/normalization rules stable to avoid breaking client expectations.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from agentic_scraper.backend.config.messages import MSG_ERROR_EMPTY_STRING
from agentic_scraper.backend.utils.validators import validate_optional_str

__all__ = [
    "UserCredentialsIn",
    "UserCredentialsOut",
    "UserCredentialsStatus",
    "UserProfile",
]


class UserCredentialsIn(BaseModel):
    """
    Input schema for saving a user's OpenAI credentials.

    Attributes:
        api_key (SecretStr): User's OpenAI API key. Accepted as a secret type,
            ensuring it is redacted from logs and error messages.
        project_id (str): User's OpenAI project ID. Must be a non-empty string.

    Notes:
        - `api_key` is stored securely and never logged in cleartext.
        - `project_id` is stripped of leading/trailing whitespace before validation.
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
        """
        Strip whitespace and reject empty project IDs.

        Args:
            v (str): Raw project_id input.

        Returns:
            str: Cleaned project_id string.

        Raises:
            ValueError: If project_id is not a string or is empty after stripping.

        Examples:
            >>> UserCredentialsIn._strip_project_id("  proj_1  ")
            'proj_1'
        """
        v = v.strip() if isinstance(v, str) else v
        if not isinstance(v, str) or not v:
            # Keep message simple; deeper validation handled in store validators if needed.
            raise ValueError(MSG_ERROR_EMPTY_STRING.format(field="project_id"))
        return v


class UserCredentialsOut(BaseModel):
    """
    Output schema for returning the user's OpenAI credentials.

    Attributes:
        api_key (str): Masked string (e.g., only last 4 chars visible).
        project_id (str): OpenAI project ID.
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
    """
    Presence info for stored credentials.

    Attributes:
        has_credentials (bool): Whether the user has saved OpenAI credentials.
    """

    model_config = ConfigDict(extra="ignore")

    has_credentials: bool = Field(
        ...,
        description="Whether the user has saved OpenAI credentials.",
        json_schema_extra={"example": True},
    )


class UserProfile(BaseModel):
    """
    Represents the authenticated user's profile.

    Attributes:
        sub (str): User unique identifier (subject claim from Auth0).
        email (EmailStr | None): User's email address, if available.
        name (str | None): Human-readable full name, if available.
    """

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
        """
        Strip whitespace and reject empty subject values.

        Args:
            v (str): Raw subject string.

        Returns:
            str: Cleaned subject string.

        Raises:
            ValueError: If sub is missing or empty after stripping.

        Examples:
            >>> UserProfile._clean_sub("  auth0|abc123  ")
            'auth0|abc123'
        """
        s = v.strip() if isinstance(v, str) else v
        if not isinstance(s, str) or not s:
            raise ValueError(MSG_ERROR_EMPTY_STRING.format(field="sub"))
        return s

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, v: str | None) -> str | None:
        """
        Normalize optional name fields by stripping whitespace and rejecting empties.

        Args:
            v (str | None): Raw name input.

        Returns:
            str | None: Cleaned name string or None.

        Raises:
            ValueError: If the name is an empty string after trimming.

        Examples:
            >>> UserProfile._clean_name("  Dana  ")
            'Dana'
            >>> UserProfile._clean_name("   ")
            None
        """
        if v is None:
            return None
        if not isinstance(v, str):
            return v  # Let Pydantic handle type errors.
        trimmed = v.strip()
        return validate_optional_str(trimmed, "name")
