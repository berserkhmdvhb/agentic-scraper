from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from agentic_scraper.backend.api.schemas.items import (
    ScrapedItemDynamicDTO,
    ScrapedItemFixedDTO,
)
from agentic_scraper.backend.config.messages import MSG_ERROR_MISSING_FIELDS_FOR_AGENT
from agentic_scraper.backend.config.types import (
    AgentMode,
    JobStatus,
    OpenAIConfig,
    OpenAIModel,
)

if TYPE_CHECKING:
    from agentic_scraper.backend.scraper.schemas import ScrapedItem

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
    Request payload for initiating a scrape job.

    Validates that OpenAI-related fields are present when using an LLM-based
    agent mode (non-rule-based).
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
        mode_value = getattr(self.agent_mode, "value", self.agent_mode)
        if mode_value == AgentMode.RULE_BASED:
            return self

        missing: list[str] = []
        if self.openai_model is None:
            missing.append("openai_model")
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


class ScrapeResultBase(BaseModel):
    """Base model for scrape results returned in job responses."""

    stats: Mapping[str, object] = Field(
        ..., description="Execution metrics (counts, duration, etc.)"
    )


class ScrapeResultFixed(ScrapeResultBase):
    """
    Scrape results for agents using a fixed schema.

    Typically produced by `AgentMode.LLM_FIXED` or `AgentMode.RULE_BASED`.
    """

    items: list[ScrapedItemFixedDTO] = Field(..., description="Extracted items from all URLs.")

    @classmethod
    def from_internal(
        cls,
        items: list[ScrapedItem],
        stats: Mapping[str, object],
    ) -> ScrapeResultFixed:
        """Convert internal scraper models to API DTOs."""
        return cls(
            items=[ScrapedItemFixedDTO.from_internal(i) for i in items],
            stats=stats,
        )


class ScrapeResultDynamic(ScrapeResultBase):
    """
    Scrape results for agents using a dynamic schema.

    Typically produced by `AgentMode.DYNAMIC_LLM`.
    """

    items: list[ScrapedItemDynamicDTO] = Field(
        ..., description="Extracted items from all URLs, may include extra fields."
    )

    @classmethod
    def from_internal(
        cls,
        items: list[ScrapedItem],
        stats: Mapping[str, object],
    ) -> ScrapeResultDynamic:
        """Convert internal scraper models to API DTOs."""
        return cls(
            items=[ScrapedItemDynamicDTO.from_internal(i) for i in items],
            stats=stats,
        )


class ScrapeJob(BaseModel):
    """
    Represents a scrape job with its current state.

    The `result` type depends on the agent mode used:
    - Fixed schema → `ScrapeResultFixed`
    - Dynamic schema → `ScrapeResultDynamic`
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
    # NOTE: Order matters. Pydantic tries union variants in order.
    result: ScrapeResultDynamic | ScrapeResultFixed | None = Field(
        default=None, description="Present when status == 'succeeded'."
    )


class ScrapeList(BaseModel):
    """Paginated list of scrape jobs."""

    items: list[ScrapeJob]
    next_cursor: str | None = None
