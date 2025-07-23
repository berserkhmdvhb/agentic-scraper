from typing import Annotated, Any

from pydantic import BaseModel, Field, HttpUrl

from agentic_scraper.backend.scraper.models import ScrapedItem

UrlsType = Annotated[
    list[HttpUrl],
    Field(
        min_items=1, description="List of URLs to scrape", examples=[["https://example.com/page1"]]
    ),
]


class ScrapeRequest(BaseModel):
    urls: UrlsType


class ScrapeResponse(BaseModel):
    results: list[ScrapedItem] = Field(..., description="List of extracted items from all URLs")
    stats: dict[str, Any] = Field(
        ..., description="Metadata such as execution time, errors, and item counts"
    )
