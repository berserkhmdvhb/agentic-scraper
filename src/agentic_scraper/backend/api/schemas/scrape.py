from typing import Annotated, Any
from pydantic import BaseModel, Field, HttpUrl, model_validator
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
    openai_credentials: OpenAIConfig | None = None
    fetch_concurrency: int
    llm_concurrency: int | None = None
    screenshot_enabled: bool
    verbose: bool
    openai_model: OpenAIModel | None = None
    agent_mode: AgentMode
    retry_attempts: int
    llm_schema_retries: int | None = None

    @model_validator(mode="after")
    def validate_openai_fields(self) -> "ScrapeRequest":
        """Ensure OpenAI fields are present when agent_mode is not rule_based."""
        if self.agent_mode != "rule_based":
            missing = []
            if self.openai_model is None:
                missing.append("openai_model")
            if self.openai_credentials is None:
                missing.append("openai_credentials")
            if self.llm_concurrency is None:
                missing.append("llm_concurrency")
            if self.llm_schema_retries is None:
                missing.append("llm_schema_retries")
            if missing:
                raise ValueError(
                    f"Missing required fields for agent_mode '{self.agent_mode}': {', '.join(missing)}."
                )
        return self


class ScrapeResponse(BaseModel):
    results: list[ScrapedItem] = Field(..., description="List of extracted items from all URLs")
    stats: dict[str, Any] = Field(
        ..., description="Metadata such as execution time, errors, and item counts"
    )
