from pydantic import BaseModel, Field, HttpUrl


class ScrapedItem(BaseModel):
    """The structured output from scraping a single webpage."""

    url: HttpUrl
    title: str | None = Field(default=None, description="Main title or heading")
    description: str | None = Field(default=None, description="Short description or summary")
    price: float | None = Field(default=None, description="Numeric price if detected")
    author: str | None = Field(default=None, description="Author or source of the content")
    date_published: str | None = Field(default=None, description="Publication date if known")
    screenshot_path: str | None = Field(default=None, description="Path to screenshot image")

    class Config:
        extra = "allow"  # Allow LLM to return more fields than expected
