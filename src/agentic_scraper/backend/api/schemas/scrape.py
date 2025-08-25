from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from agentic_scraper.backend.api.schemas.items import (
    ScrapedItemDynamicDTO,
    ScrapedItemFixedDTO,
)
from agentic_scraper.backend.config.constants import (
    DEFAULT_AGENT_MODE,
    DEFAULT_FETCH_CONCURRENCY,
    DEFAULT_LLM_CONCURRENCY,
    DEFAULT_LLM_SCHEMA_RETRIES,
    MAX_URLS_PER_REQUEST,
)
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_MISSING_FIELDS_FOR_AGENT,
    MSG_ERROR_URLS_MUST_BE_LIST,
)
from agentic_scraper.backend.config.types import (
    AgentMode,
    JobStatus,
    OpenAIConfig,
    OpenAIModel,
)
from agentic_scraper.backend.utils.validators import validate_url_list

if TYPE_CHECKING:
    from agentic_scraper.backend.scraper.schemas import ScrapedItem


UrlsType = Annotated[
    list[HttpUrl],
    Field(
        min_length=1,
        description="List of URLs to scrape.",
        examples=[["https://example.com/page1", "https://example.com/page2"]],
    ),
]


class ScrapeCreate(BaseModel):
    """
    Request payload for initiating a scrape job.

    Notes:
      - `urls` are normalized (trimmed, deduped, bounded by MAX_URLS_PER_REQUEST) before validation.
      - LLM-based modes (non-rule-based) require only `openai_model` explicitly;
        `llm_concurrency` and `llm_schema_retries` use sensible defaults.
    """

    urls: UrlsType
    agent_mode: AgentMode = Field(
        DEFAULT_AGENT_MODE, description="Agent mode to use for the scrape."
    )
    openai_model: OpenAIModel | None = None
    openai_credentials: OpenAIConfig | None = None

    # Defaults + bounds for concurrency knobs
    llm_concurrency: int = Field(DEFAULT_LLM_CONCURRENCY, ge=1, description="Parallel LLM calls.")
    llm_schema_retries: int = Field(
        DEFAULT_LLM_SCHEMA_RETRIES, ge=0, description="Retries for LLM schema validation."
    )
    fetch_concurrency: int = Field(
        DEFAULT_FETCH_CONCURRENCY, ge=1, description="Parallel fetch workers."
    )

    screenshot_enabled: bool = False
    verbose: bool = False
    retry_attempts: int = Field(0, ge=0, description="Non-LLM retry attempts.")

    @field_validator("urls", mode="before")
    @classmethod
    def _normalize_urls(cls, v: object) -> list[str] | object:
        """
        Accept list[str|HttpUrl], dedupe & trim with validator, then allow Pydantic
        to re-validate each item as HttpUrl.
        """
        if isinstance(v, list):
            return validate_url_list(
                [str(u) for u in v],
                min_len=1,
                max_len=MAX_URLS_PER_REQUEST,
                dedupe=True,
            )
        # Make type errors explicit (helps clients and avoids ambiguous coercion).
        raise TypeError(MSG_ERROR_URLS_MUST_BE_LIST)

    @model_validator(mode="after")
    def validate_openai_fields(self) -> ScrapeCreate:
        # Require only openai_model for non-rule-based modes (defaults cover the rest).
        if self.agent_mode == AgentMode.RULE_BASED:
            return self

        if self.openai_model is None:
            raise ValueError(
                MSG_ERROR_MISSING_FIELDS_FOR_AGENT.format(
                    agent_mode=self.agent_mode.value,
                    missing_fields="openai_model",
                )
            )
        return self


class ScrapeResultBase(BaseModel):
    """Base model for scrape results returned in job responses."""

    stats: dict[str, Any] = Field(..., description="Execution metrics (counts, duration, etc.)")


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
        stats: dict[str, Any],
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
        stats: dict[str, Any],
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

    model_config = ConfigDict(
        extra="ignore",
        use_enum_values=True,  # Ensure enums serialize as their values on the wire
    )

    id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    progress: float | None = Field(
        default=None, ge=0.0, le=1.0, description="0..1 progress while running."
    )
    error: str | None = Field(default=None, description="Populated when status == 'failed'.")
    # NOTE: Order matters if you keep a plain union; consider a discriminator in future.
    result: ScrapeResultDynamic | ScrapeResultFixed | None = Field(
        default=None, description="Present when status == 'succeeded'."
    )


class ScrapeList(BaseModel):
    """Paginated list of scrape jobs."""

    model_config = ConfigDict(
        extra="ignore",
        use_enum_values=True,
    )

    items: list[ScrapeJob]
    next_cursor: str | None = None
