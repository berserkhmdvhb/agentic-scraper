from typing import Annotated, Any

from pydantic import BaseModel, Field, HttpUrl, model_validator

from agentic_scraper.backend.config.messages import MSG_ERROR_MISSING_FIELDS_FOR_AGENT
from agentic_scraper.backend.config.types import AgentMode, OpenAIModel
from agentic_scraper.backend.scraper.models import OpenAIConfig, ScrapedItem

UrlsType = Annotated[
    list[HttpUrl],
    Field(
        min_items=1,
        description="List of URLs to scrape",
        examples=[["https://example.com/page1"]],
    ),
]


class ScrapeRequest(BaseModel):
    urls: list[str]
    agent_mode: AgentMode
    openai_model: OpenAIModel | None = None
    openai_credentials: OpenAIConfig | None = None
    llm_concurrency: int | None = None
    llm_schema_retries: int | None = None
    fetch_concurrency: int
    screenshot_enabled: bool
    verbose: bool
    retry_attempts: int

    @model_validator(mode="after")
    def validate_openai_fields(self) -> "ScrapeRequest":
        if self.agent_mode == AgentMode.RULE_BASED:
            # Skip validation if rule_based — allow all OpenAI fields to be None
            return self

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
                MSG_ERROR_MISSING_FIELDS_FOR_AGENT.format(
                    agent_mode=self.agent_mode, missing_fields=", ".join(missing)
                )
            )

        return self


class ScrapeResponse(BaseModel):
    results: list[ScrapedItem] = Field(..., description="List of extracted items from all URLs")
    stats: dict[str, Any] = Field(
        ..., description="Metadata such as execution time, errors, and item counts"
    )
