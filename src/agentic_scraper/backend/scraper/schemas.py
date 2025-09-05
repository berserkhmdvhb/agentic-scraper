"""
Schemas for structured scraper outputs and pipeline execution stats.

Responsibilities:
- Define the internal shape of a scraped item (`ScrapedItem`).
- Capture aggregated metrics for a scrape run (`PipelineStats`).
- Provide a standardized envelope for scraper results (`PipelineOutput`).

Models:
- `ScrapedItem`: Structured data for one page (url, title, description, price, etc.).
- `PipelineStats`: Execution counters and duration.
- `PipelineOutput`: Container for items + stats.

Validation:
- URLs validated/normalized (http/https only).
- Empty strings normalized to `None` for optional text fields.
- Price values parsed from text and enforced to be non-negative.
- Stat counters must be non-negative ints; duration must be non-negative float.

Usage:
    from agentic_scraper.backend.scraper.schemas import ScrapedItem, PipelineOutput

    item = ScrapedItem(url="https://example.com", title="Sample")
    stats = PipelineStats(total_urls=1, succeeded=1, failed=0, duration_sec=0.5)
    output = PipelineOutput(items=[item], stats=stats)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agentic_scraper.backend.config.messages import MSG_ERROR_INVALID_LIMIT
from agentic_scraper.backend.utils.validators import (
    clean_price,
    validate_optional_str,
    validate_price,
    validate_url,
)

__all__ = ["PipelineOutput", "PipelineStats", "ScrapedItem"]


class ScrapedItem(BaseModel):
    """
    Internal representation of structured data extracted from a single web page.

    Attributes:
        url (str): Page URL (validated to http/https).
        title (str | None): Main title or heading.
        description (str | None): Short description or summary.
        price (float | None): Numeric price if detected.
        author (str | None): Author or content source.
        date_published (str | None): Publication date string, if known.
        screenshot_path (str | None): Optional screenshot file path.

    Notes:
        - Extra keys are allowed to accommodate dynamic agent outputs.
        - Empty strings are normalized to `None` for optionals.
    """

    url: str
    title: str | None = Field(default=None, description="Main title or heading")
    description: str | None = Field(default=None, description="Short description or summary")
    price: float | None = Field(default=None, description="Numeric price if detected")
    author: str | None = Field(default=None, description="Author or source of the content")
    date_published: str | None = Field(default=None, description="Publication date if known")
    screenshot_path: str | None = Field(default=None, description="Path to screenshot image")

    # URL validation (http/https and trimmed)
    _url_check = field_validator("url", mode="before")(validate_url)

    # Cleaning / normalization of optionals (reject empty strings)
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
    _clean_screenshot = field_validator("screenshot_path", mode="before")(
        lambda v: validate_optional_str(v, "screenshot_path")
    )

    # Price parsing and enforcement (clean string → float; non-negative)
    _clean_price_text = field_validator("price", mode="before")(clean_price)
    _enforce_price_non_negative = field_validator("price", mode="after")(validate_price)

    # Allow extra keys for dynamic agent outputs
    model_config = ConfigDict(extra="allow")


class PipelineStats(BaseModel):
    """
    Aggregated execution stats for a scrape pipeline run.

    Attributes:
        total_urls (int): Total number of URLs processed.
        succeeded (int): Count of successful extractions.
        failed (int): Count of failed extractions.
        duration_sec (float): Duration in seconds.
    """

    total_urls: int
    succeeded: int
    failed: int
    duration_sec: float

    @field_validator("total_urls", "succeeded", "failed", mode="before")
    @classmethod
    def _non_negative_int(cls, v: int) -> int:
        if not isinstance(v, int) or v < 0:
            raise ValueError(MSG_ERROR_INVALID_LIMIT.format(value=v, min=0, max=10_000_000))
        return v

    @field_validator("duration_sec", mode="before")
    @classmethod
    def _non_negative_duration(cls, v: float) -> float:
        if not isinstance(v, (int, float)) or float(v) < 0.0:
            raise ValueError(MSG_ERROR_INVALID_LIMIT.format(value=v, min=0, max=10_000_000))
        return float(v)


class PipelineOutput(BaseModel):
    """
    Standardized pipeline result shape used internally by the scraper layer.

    Attributes:
        items (list[ScrapedItem]): The list of structured items extracted.
        stats (PipelineStats): Aggregated execution statistics.
    """

    items: list[ScrapedItem]
    stats: PipelineStats
