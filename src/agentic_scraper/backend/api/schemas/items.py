from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from agentic_scraper.backend.utils.validators import validate_optional_str

if TYPE_CHECKING:
    from agentic_scraper.backend.scraper.schemas import ScrapedItem


class _ScrapedItemBaseDTO(BaseModel):
    """Common API-facing fields for all scraped items."""

    url: HttpUrl
    title: str | None = Field(default=None, description="Main title or heading.")
    description: str | None = Field(default=None, description="Short description or summary.")
    price: float | None = Field(default=None, description="Numeric price if detected.")
    author: str | None = Field(default=None, description="Author or source of the content.")
    date_published: str | None = Field(default=None, description="Publication date if known.")
    screenshot_path: str | None = Field(default=None, description="Path to screenshot image.")

    # Normalize optional strings to avoid leaking empty strings in API responses
    _clean_title = field_validator("title", mode="before")(
        lambda v: validate_optional_str(v, "title")
    )
    _clean_description = field_validator("description", mode="before")(
        lambda v: validate_optional_str(v, "description")
    )
    _clean_author = field_validator("author", mode="before")(
        lambda v: validate_optional_str(v, "author")
    )
    _clean_date = field_validator("date_published", mode="before")(
        lambda v: validate_optional_str(v, "date_published")
    )
    _clean_screenshot = field_validator("screenshot_path", mode="before")(
        lambda v: validate_optional_str(v, "screenshot_path")
    )

    model_config = ConfigDict(extra="ignore")  # API schema is fixed unless overridden


class ScrapedItemFixedDTO(_ScrapedItemBaseDTO):
    """DTO for fixed-schema extractions — no extra fields allowed."""

    @classmethod
    def from_internal(cls, item: ScrapedItem) -> ScrapedItemFixedDTO:
        """Convert internal scraper model to fixed-schema API DTO."""
        return cls.model_validate(item.model_dump())


class ScrapedItemDynamicDTO(_ScrapedItemBaseDTO):
    """DTO for dynamic-schema extractions — allows extra fields returned by LLM agents."""

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_internal(cls, item: ScrapedItem) -> ScrapedItemDynamicDTO:
        """Convert internal scraper model to dynamic-schema API DTO."""
        # keep all extra fields from internal model
        return cls.model_validate(item.model_dump())


__all__ = [
    "ScrapedItemDynamicDTO",
    "ScrapedItemFixedDTO",
]
