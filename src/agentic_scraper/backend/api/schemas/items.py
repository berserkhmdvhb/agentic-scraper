"""
API schemas for scraped items (DTOs).

Models:
- `ScrapedItemFixedDTO`: Strict, fixed-schema DTO exposing canonical fields.
- `ScrapedItemDynamicDTO`: Flexible DTO that permits additional fields for adaptive agents.

Serialization:
- Empty strings for optional text fields are normalized to `None` via validators.
- `ScrapedItemFixedDTO` ignores unknown fields; `ScrapedItemDynamicDTO` allows them.
- DTOs support `.model_dump()` for wire serialization.

Validation & Defaults:
- Pydantic validators coerce/clean optional strings prior to model validation.
- Extra fields are ignored by default; dynamic DTO opts in to `extra="allow"`.

Usage:
    from agentic_scraper.backend.api.schemas.items import ScrapedItemFixedDTO

    dto = ScrapedItemFixedDTO.from_internal(internal_item)
    payload = dto.model_dump()

Notes:
- These DTOs are API-facing and may evolve deliberately more slowly than internal models.
- Keep normalization rules stable to avoid surprising API consumers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from agentic_scraper.backend.utils.validators import validate_optional_str

if TYPE_CHECKING:
    from agentic_scraper.backend.scraper.schemas import ScrapedItem

__all__ = [
    "ScrapedItemDynamicDTO",
    "ScrapedItemFixedDTO",
]


class _ScrapedItemBaseDTO(BaseModel):
    """
    Common API-facing fields for all scraped items.

    This base schema includes canonical fields expected for most scraped items
    (title, description, price, etc.). Both fixed and dynamic DTOs subclass it.

    Attributes:
        url (HttpUrl): Source URL of the scraped item.
        title (str | None): Main title or heading.
        description (str | None): Short description or summary.
        price (float | None): Numeric price if detected.
        author (str | None): Author or source of the content.
        date_published (str | None): Publication date if known.
        screenshot_path (str | None): Path to screenshot image.

    Notes:
        - Validators normalize empty strings into `None`.
        - Extra fields are ignored by default; see subclass overrides.
    """

    url: HttpUrl
    title: str | None = Field(default=None, description="Main title or heading.")
    description: str | None = Field(default=None, description="Short description or summary.")
    price: float | None = Field(default=None, description="Numeric price if detected.")
    author: str | None = Field(default=None, description="Author or source of the content.")
    date_published: str | None = Field(default=None, description="Publication date if known.")
    screenshot_path: str | None = Field(default=None, description="Path to screenshot image.")

    # Normalize optional strings to avoid leaking empty strings in API responses.
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

    # By default, ignore unknown fields (strict DTOs should not surface internals by accident).
    # The dynamic DTO overrides this to allow additional fields.
    model_config = ConfigDict(extra="ignore")


class ScrapedItemFixedDTO(_ScrapedItemBaseDTO):
    """
    DTO for fixed-schema extractions.

    This representation enforces a strict contract — only the known fields from
    `_ScrapedItemBaseDTO` are accepted. Used when extraction agents operate with
    a predefined schema.
    """

    @classmethod
    def from_internal(cls, item: ScrapedItem) -> ScrapedItemFixedDTO:
        """
        Convert an internal scraper model to a fixed-schema API DTO.

        Args:
            item (ScrapedItem): Internal scraper model.

        Returns:
            ScrapedItemFixedDTO: Equivalent API-facing DTO.

        Raises:
            pydantic.ValidationError: If the internal data cannot be coerced into the DTO.

        Examples:
            >>> dto = ScrapedItemFixedDTO.from_internal(item)
            >>> dto.model_dump()
            {'url': 'https://example.com', 'title': 'T', ...}
        """
        # We trust the internal schema shape and rely on Pydantic for coercion/validation.
        return cls.model_validate(item.model_dump())


class ScrapedItemDynamicDTO(_ScrapedItemBaseDTO):
    """
    DTO for dynamic-schema extractions.

    This representation allows extra fields returned by LLM-based agents to pass
    through to API clients. It is useful for adaptive or exploratory scraping modes
    where the schema is not fixed.
    """

    # Allow additional, non-standard fields to be included in the API payload.
    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_internal(cls, item: ScrapedItem) -> ScrapedItemDynamicDTO:
        """
        Convert an internal scraper model to a dynamic-schema API DTO.

        Args:
            item (ScrapedItem): Internal scraper model.

        Returns:
            ScrapedItemDynamicDTO: Equivalent API-facing DTO, including extra fields.

        Raises:
            pydantic.ValidationError: If required base fields are invalid.

        Examples:
            >>> dto = ScrapedItemDynamicDTO.from_internal(item)
            >>> x = dto.model_dump()
            >>> "custom_field" in x  # preserved if present internally
            True
        """
        # Preserve all extra fields from the internal model payload.
        return cls.model_validate(item.model_dump())
