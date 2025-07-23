from typing import Any

from pydantic import BaseModel

from agentic_scraper.backend.scraper.models import ScrapedItem


class ScrapeRequest(BaseModel):
    urls: list[str]


class ScrapeResponse(BaseModel):
    results: list[ScrapedItem]
    stats: dict[str, Any]
