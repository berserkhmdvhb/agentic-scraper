from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from agentic_scraper.backend.api.schemas.items import ScrapedItemDTO
from agentic_scraper.backend.config.messages import MSG_ERROR_MISSING_FIELDS_FOR_AGENT
from agentic_scraper.backend.config.types import (
    AgentMode,
    JobStatus,
    OpenAIConfig,
    OpenAIModel,
)

# Reusable type for URL lists with validation and examples
UrlsType = Annotated[
    list[HttpUrl],
    Field(
        min_items=1,
        description="List of URLs to scrape.",
        examples=[["https://example.com/page1", "https://example.com/page2"]],
    ),
]


class ScrapeCreate(BaseModel):
    """
    Request payload to create a new scrape job.

    Args:
        urls (list[HttpUrl]): URLs to scrape.
        agent_mode (AgentMode): Extraction mode (e.g., adaptive, fixed, rule-based).
        openai_model (OpenAIModel | None): Model used when an LLM agent is selected.
        openai_credentials (OpenAIConfig | None): Optional per-request OpenAI credentials.
        llm_concurrency (int | None): LLM parallelism; required for LLM agents.
        llm_schema_retries (int | None): Schema retries for adaptive/fixed agents.
        fetch_concurrency (int): Parallel fetch limit.
        screenshot_enabled (bool): Capture screenshots during scraping.
        verbose (bool): Increase logging/verbosity.
        retry_attempts (int): Non-LLM retry attempts where applicable.
    """

    urls: UrlsType
    agent_mode: AgentMode
    openai_model: OpenAIModel | None = None
    openai_credentials: OpenAIConfig | None = None
    llm_concurrency: int | None = None
    llm_schema_retries: int | None = None
    fetch_concurrency: int = Field(..., ge=1, description="Parallel fetch workers.")
    screenshot_enabled: bool = False
    verbose: bool = False
    retry_attempts: int = Field(0, ge=0, description="Non-LLM retry attempts.")

    @model_validator(mode="after")
    def validate_openai_fields(self) -> ScrapeCreate:
        """
        Enforce OpenAI-related fields only when an LLM agent is selected.
        Rule-based mode may omit all OpenAI fields.

        Returns:
            ScrapeCreate: The validated model.
        """
        # Works whether AgentMode is an Enum or Literal[str]
        mode_value = getattr(self.agent_mode, "value", self.agent_mode)
        if mode_value == "rule_based":
            return self

        missing: list[str] = []
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
                    agent_mode=mode_value, missing_fields=", ".join(missing)
                )
            )

        return self


class ScrapeResult(BaseModel):
    """
    Final job result payload returned when a job has succeeded.

    Args:
        items (list[ScrapedItemDTO]): Extracted items across all URLs.
        stats (dict[str, object]): Aggregated metrics (e.g., totals, duration).
    """

    items: list[ScrapedItemDTO] = Field(..., description="Extracted items from all URLs.")
    stats: dict[str, object] = Field(..., description="Execution metrics (counts, duration, etc.).")


class ScrapeJob(BaseModel):
    """
    Representation of a scrape job resource for polling.

    Args:
        id (str): Unique job identifier.
        status (JobStatus): Current state of the job.
        created_at (datetime): Creation timestamp (UTC).
        updated_at (datetime): Last update timestamp (UTC).
        progress (float | None): 0..1 progress indicator while running.
        error (str | None): Error message if the job failed.
        result (ScrapeResult | None): Final result when status == 'succeeded'.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    progress: float | None = Field(
        default=None, ge=0.0, le=1.0, description="0..1 progress while running."
    )
    error: str | None = Field(default=None, description="Populated when status == 'failed'.")
    result: ScrapeResult | None = Field(
        default=None, description="Present when status == 'succeeded'."
    )


class ScrapeList(BaseModel):
    items: list[ScrapeJob]
    next_cursor: str | None = None
