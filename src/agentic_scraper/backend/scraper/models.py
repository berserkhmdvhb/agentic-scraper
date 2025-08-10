from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from agentic_scraper.backend.config.aliases import (
    OnErrorCallback,
    OnSuccessCallback,
)
from agentic_scraper.backend.utils.validators import (
    clean_price,
    validate_optional_str,
)


class ScrapedItem(BaseModel):
    """
    Represents structured data extracted from a single web page.

    This model is returned by all scraping agents. It includes common fields such as title,
    description, price, and publication metadata. Extra fields from the LLM are allowed.

    Fields:
        url (HttpUrl): Source URL of the page.
        title (str | None): Main title or heading.
        description (str | None): Short description or summary.
        price (float | None): Numeric price if detected.
        author (str | None): Author or source of the content.
        date_published (str | None): Publication date if known.
        screenshot_path (str | None): Path to a captured screenshot image.
    """

    url: HttpUrl
    title: str | None = Field(default=None, description="Main title or heading")
    description: str | None = Field(default=None, description="Short description or summary")
    price: float | None = Field(default=None, description="Numeric price if detected")
    author: str | None = Field(default=None, description="Author or source of the content")
    date_published: str | None = Field(default=None, description="Publication date if known")
    screenshot_path: str | None = Field(default=None, description="Path to screenshot image")

    _clean_title = field_validator("title", mode="before")(
        lambda v: validate_optional_str(v, "title")
    )
    _clean_description = field_validator("description", mode="before")(
        lambda v: validate_optional_str(v, "description")
    )
    _clean_author = field_validator("author", mode="before")(
        lambda v: validate_optional_str(v, "author")
    )
    _clean_date = field_validator("date_published", mode="before")(
        lambda v: validate_optional_str(v, "date_published")
    )
    _clean_price = field_validator("price", mode="before")(clean_price)
    _clean_screenshot = field_validator("screenshot_path", mode="before")(
        lambda v: validate_optional_str(v, "screenshot_path")
    )

    # Pydantic v2 configuration: allow extra fields returned by the LLM.
    model_config = ConfigDict(extra="allow")


class OpenAIConfig(BaseModel):
    """
    Container for OpenAI credential configuration used by agents.

    Fields:
        api_key (str | None): API key if provided per-request.
        project_id (str | None): Project ID if provided per-request.
    """

    api_key: str | None = None
    project_id: str | None = None


class ScrapeRequest(BaseModel):
    """
    Per-URL scrape input prepared by the fetch/prepare stage.

    Args:
        text (str): Cleaned main text extracted from the HTML.
        url (str): Original URL.
        take_screenshot (bool): Whether to capture a screenshot during extraction.
        openai (OpenAIConfig | None): Optional OpenAI credentials to override defaults.
        context_hints (dict[str, str] | None): Optional hints to guide extraction.

    Returns:
        ScrapeRequest: Validated request for an agent to process.
    """

    text: str
    url: str
    take_screenshot: bool = False
    openai: OpenAIConfig | None = None
    context_hints: dict[str, str] | None = None


@dataclass
class RetryContext:
    """
    Mutable context passed through adaptive LLM retries to track best candidates.

    Attributes:
        messages (list[ChatCompletionMessageParam]): Prompt/response message chain.
        best_score (float): Highest score observed among all attempts (may be invalid).
        best_valid_score (float): Highest score among schema-valid items.
        best_fields (dict[str, Any] | None): Raw best field map (may be invalid).
        best_valid_item (ScrapedItem | None): Best validated item, if any.
        all_fields (dict[str, Any]): Latest raw field map from the LLM.
        has_done_discovery (bool): Whether a discovery retry has been attempted.
    """

    messages: list[ChatCompletionMessageParam]
    best_score: float
    best_valid_score: float
    best_fields: dict[str, Any] | None
    best_valid_item: ScrapedItem | None
    all_fields: dict[str, Any]
    has_done_discovery: bool = False


class PipelineStats(BaseModel):
    """
    Aggregated execution stats for a scrape pipeline run.

    Fields:
        total_urls (int): Number of URLs submitted to the pipeline.
        succeeded (int): Number of successfully extracted items.
        failed (int): Number of items that failed extraction.
        duration_sec (float): Total wall-clock duration of the run in seconds.
    """

    total_urls: int
    succeeded: int
    failed: int
    duration_sec: float


class PipelineOutput(BaseModel):
    """
    Standardized pipeline result shape used internally by the scraper layer.

    Fields:
        items (list[ScrapedItem]): Extracted items in completion or input order.
        stats (PipelineStats): Aggregated metrics for the run.
    """

    items: list[ScrapedItem]
    stats: PipelineStats


@dataclass
class WorkerPoolConfig:
    """
    Configuration for running a concurrent scraping worker pool.

    Args:
        take_screenshot (bool): Whether to capture screenshots during scraping.
        openai (OpenAIConfig | None): Optional OpenAI credentials.
        concurrency (int): Number of concurrent worker tasks.
        max_queue_size (int | None): Optional limit on input queue size.
        on_item_processed (OnSuccessCallback | None): Callback on successful extraction.
        on_error (OnErrorCallback | None): Callback when an error occurs during extraction.
        on_progress (Callable[[int, int], None] | None): Progress callback with
            (processed, total) counts, invoked after each item completes.
        preserve_order (bool): If True, results are returned in input order.
            Defaults to False (completion order).

    Returns:
        WorkerPoolConfig: Immutable configuration for worker pool execution.
    """

    take_screenshot: bool
    openai: OpenAIConfig | None = None
    concurrency: int = 10
    max_queue_size: int | None = None
    on_item_processed: OnSuccessCallback | None = None
    on_error: OnErrorCallback | None = None
    on_progress: Callable[[int, int], None] | None = None
    preserve_order: bool = False
