from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_INVALID_LIMIT,
)
from agentic_scraper.backend.utils.validators import (
    clean_price,
    validate_optional_str,
    validate_price,
    validate_url,
)


class ScrapedItem(BaseModel):
    """
    Internal representation of structured data extracted from a single web page.

    Notes:
        - URL is a `str` for consistency across the scraper layer and is validated to be http(s).
        - Extra keys are allowed to accommodate dynamic agent outputs.
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
    """

    items: list[ScrapedItem]
    stats: PipelineStats
    # Optionally enforce invariants later with a model_validator.
