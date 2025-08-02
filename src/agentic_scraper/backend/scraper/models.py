from pydantic import BaseModel, Field, HttpUrl, field_validator

from agentic_scraper.backend.utils.validators import (
    clean_price,
    validate_optional_str,
)


class ScrapedItem(BaseModel):
    """
    Represents structured data extracted from a single web page.

    This model is returned by all scraping agents. It includes common fields such as title,
    description, price, and publication metadata. Extra fields from the LLM are allowed.
    """

    url: HttpUrl
    title: str | None = Field(default=None, description="Main title or heading")
    description: str | None = Field(default=None, description="Short description or summary")
    price: float | None = Field(default=None, description="Numeric price if detected")
    author: str | None = Field(default=None, description="Author or source of the content")
    date_published: str | None = Field(default=None, description="Publication date if known")
    screenshot_path: str | None = Field(default=None, description="Path to screenshot image")

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
    _clean_price = field_validator("price", mode="before")(clean_price)
    _clean_screenshot = field_validator("screenshot_path", mode="before")(
        lambda v: validate_optional_str(v, "screenshot_path")
    )

    class Config:
        """Pydantic configuration: allow extra fields returned by the LLM."""

        extra = "allow"  # Allow LLM to return more fields than expected


class OpenAIConfig(BaseModel):
    api_key: str | None = None
    project_id: str | None = None


class ScrapeRequest(BaseModel):
    text: str
    url: str
    take_screenshot: bool = False
    openai: OpenAIConfig | None = None
    context_hints: dict[str, str] | None = None