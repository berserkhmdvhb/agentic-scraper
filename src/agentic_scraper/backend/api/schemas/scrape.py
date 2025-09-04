"""
API schemas for scrape requests, results, and jobs.

Models:
- `ScrapeCreate`: Request payload to start a scraping job.
- `ScrapeResultFixed` / `ScrapeResultDynamic`: Result envelopes for fixed vs. dynamic agents.
- `ScrapeJob`: Scrape job snapshot (status, progress, result).
- `ScrapeList`: Paginated list of jobs.

Serialization:
- `ScrapeCreate.urls` are normalized prior to Pydantic coercion to `HttpUrl` for clearer errors.
- Enum fields use raw values on the wire (`use_enum_values=True` where appropriate).
- Optional text fields are normalized (empty string → `None`).

Validation & Defaults:
- URL list is deduped/trimmed/bounded before type coercion for better client feedback.
- `openai_model` is required for non-rule-based agents; concurrency knobs have sane defaults.

Usage:
    from agentic_scraper.backend.api.schemas.scrape import ScrapeCreate

    req = ScrapeCreate(urls=["https://example.com"], agent_mode="llm_fixed")
    payload = req.model_dump()

Notes:
- DTOs are API-facing; do not perform I/O.
- Non-rule-based agent modes require `openai_model`; other LLM knobs have defaults.
- For result unions, a future discriminator could make parsing more explicit on clients.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

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
from agentic_scraper.backend.utils.validators import validate_optional_str, validate_url_list

if TYPE_CHECKING:
    from agentic_scraper.backend.scraper.schemas import ScrapedItem


__all__ = [
    "ScrapeCreate",
    "ScrapeJob",
    "ScrapeList",
    "ScrapeResultBase",
    "ScrapeResultDynamic",
    "ScrapeResultFixed",
]


# Annotated type used to document constraints on the list of URLs.
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
        - `urls` are normalized (trimmed, deduped, bounded by MAX_URLS_PER_REQUEST) prior
          to Pydantic's coercion to `HttpUrl` for clearer client errors.
        - LLM-based modes (non-rule-based) require only `openai_model` explicitly; defaults
          cover `llm_concurrency` and `llm_schema_retries`.

    Attributes:
        urls (list[HttpUrl]): Target pages to scrape (1..MAX_URLS_PER_REQUEST).
        agent_mode (AgentMode): Which extraction agent to run.
        openai_model (OpenAIModel | None): Required for non-rule-based agents.
        openai_credentials (OpenAIConfig | None): Optional per-request OpenAI creds.
        llm_concurrency (int): Parallelism for LLM calls (>=1).
        llm_schema_retries (int): Retries for JSON/schema validation (>=0).
        fetch_concurrency (int): Parallelism for fetch workers (>=1).
        screenshot_enabled (bool): Capture screenshots when available.
        verbose (bool): Enable verbose logging.
        retry_attempts (int): Non-LLM retry attempts.
    """

    urls: UrlsType
    agent_mode: AgentMode = Field(
        DEFAULT_AGENT_MODE, description="Agent mode to use for the scrape."
    )
    openai_model: OpenAIModel | None = None
    openai_credentials: OpenAIConfig | None = None

    # Defaults + bounds for concurrency knobs.
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

        Args:
            v (object): Raw value provided for `urls`.

        Returns:
            list[str] | object: A list of normalized string URLs for Pydantic to convert,
            or raises a TypeError for non-list inputs.

        Raises:
            TypeError: If the input is not a list (explicit to aid client debugging).

        Examples:
            >>> ScrapeCreate._normalize_urls([" https://a.com ", "https://a.com"])
            ['https://a.com']
        """
        if isinstance(v, list):
            # Keep normalization pre-coercion so client errors point at the right index.
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
        """
        Enforce `openai_model` only for non-rule-based modes.

        Returns:
            ScrapeCreate: The validated (possibly unchanged) instance.

        Raises:
            ValueError: If `openai_model` is missing for a non-rule-based agent mode.

        Notes:
            - `AgentMode.RULE_BASED` does not require any OpenAI model/config.
        """
        # Rule-based mode does not need an OpenAI model.
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
        """
        Convert internal scraper models to a fixed-schema API result.

        Args:
            items (list[ScrapedItem]): Internal scraped items.
            stats (dict[str, Any]): Execution metrics.

        Returns:
            ScrapeResultFixed: API-facing fixed-schema result envelope.

        Notes:
            - Each internal item is validated/coerced through `ScrapedItemFixedDTO`.
        """
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
        """
        Convert internal scraper models to a dynamic-schema API result.

        Args:
            items (list[ScrapedItem]): Internal scraped items.
            stats (dict[str, Any]): Execution metrics.

        Returns:
            ScrapeResultDynamic: API-facing dynamic-schema result envelope.

        Notes:
            - Extra fields on internal items are preserved via `ScrapedItemDynamicDTO`.
        """
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
        use_enum_values=True,  # Ensure enums serialize as their values on the wire.
    )

    id: UUID4
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

    @field_validator("error", mode="before")
    @classmethod
    def _clean_error(cls, v: str | None) -> str | None:
        """
        Normalize empty-string errors to None so clients don't need to special-case blanks.

        Args:
            v (str | None): Raw error value.

        Returns:
            str | None: Cleaned error value.

        Examples:
            >>> ScrapeJob._clean_error("")
            None
        """
        return validate_optional_str(v, "error")


class ScrapeList(BaseModel):
    """
    Paginated list of scrape jobs.

    Attributes:
        items (list[ScrapeJob]): The page of jobs.
        next_cursor (str | None): Opaque cursor for fetching the next page, if any.
    """

    model_config = ConfigDict(
        extra="ignore",
        use_enum_values=True,
    )

    items: list[ScrapeJob]
    next_cursor: str | None = None
