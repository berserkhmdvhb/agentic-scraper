from typing import Annotated, Any
from pydantic import BaseModel, Field, HttpUrl
from agentic_scraper.backend.scraper.models import ScrapedItem, OpenAIConfig
from agentic_scraper.backend.config.types import AgentMode, OpenAIModel

UrlsType = Annotated[
    list[HttpUrl],
    Field(
        min_items=1,
        description="List of URLs to scrape",
        examples=[["https://example.com/page1"]],
    ),
]


class ScrapeRequest(BaseModel):
    urls: UrlsType
    openai_credentials: OpenAIConfig
    fetch_concurrency: int
    llm_concurrency: int
    screenshot_enabled: bool
    verbose: bool
    openai_model: OpenAIModel
    agent_mode: AgentMode
    retry_attempts: int
    llm_schema_retries: int


class ScrapeResponse(BaseModel):
    results: list[ScrapedItem] = Field(..., description="List of extracted items from all URLs")
    stats: dict[str, Any] = Field(
        ..., description="Metadata such as execution time, errors, and item counts"
    )
