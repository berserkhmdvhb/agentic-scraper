from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ScrapedItemDTO(BaseModel):
    """
    API-facing representation of a scraped item.

    Deliberately decoupled from `backend.scraper.schemas.ScrapedItem` so the
    public OpenAPI schema doesn't pull in scraper internals.

    Fields:
        url (HttpUrl): Source URL of the page.
        title (str | None): Main title or heading.
        description (str | None): Short description or summary.
        price (float | None): Numeric price if detected.
        author (str | None): Author or source of the content.
        date_published (str | None): Publication date if known.
        screenshot_path (str | None): Path to a captured screenshot image.
    """

    url: HttpUrl
    title: str | None = Field(default=None, description="Main title or heading.")
    description: str | None = Field(default=None, description="Short description or summary.")
    price: float | None = Field(default=None, description="Numeric price if detected.")
    author: str | None = Field(default=None, description="Author or source of the content.")
    date_published: str | None = Field(default=None, description="Publication date if known.")
    screenshot_path: str | None = Field(default=None, description="Path to screenshot image.")

    # Ignore extra keys that agents may return; keeps API payload stable.
    model_config = ConfigDict(extra="ignore")


__all__ = ["ScrapedItemDTO"]
