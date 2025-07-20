from pydantic import BaseModel, Field, HttpUrl, field_validator

from agentic_scraper.backend.utils.validators import validate_optional_str, validate_price


class ScrapedItem(BaseModel):
    """The structured output from scraping a single webpage."""

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
    _check_price = field_validator("price")(validate_price)

    _clean_screenshot = field_validator("screenshot_path", mode="before")(
        lambda v: validate_optional_str(v, "screenshot_path")
    )

    class Config:
        # Allow LLM to return more fields than expected
        extra = "allow"
