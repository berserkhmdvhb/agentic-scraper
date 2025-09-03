from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, field_validator

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_EMPTY_STRING,
    MSG_ERROR_INVALID_LIMIT,
)
from agentic_scraper.backend.config.types import OpenAIConfig
from agentic_scraper.backend.utils.validators import validate_url

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

    from agentic_scraper.backend.scraper.schemas import ScrapedItem


class ScrapeRequest(BaseModel):
    """
    Per-URL scrape input prepared by the fetch/prepare stage.

    Note:
        - URL is kept as `str` internally for frictionless use across agents/helpers.
          It is validated to be http(s) and trimmed.
        - `openai` accepts an `OpenAIConfig` or a compatible `dict` which will be coerced.
    """

    text: str
    url: str
    take_screenshot: bool = False
    openai: OpenAIConfig | None = None
    context_hints: dict[str, str] | None = None

    @field_validator("url", mode="before")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        return validate_url(v)

    @field_validator("text", mode="before")
    @classmethod
    def _validate_text(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(MSG_ERROR_EMPTY_STRING.format(field="text"))
        return v.strip()

    @field_validator("context_hints", mode="before")
    @classmethod
    def _clean_context_hints(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """
        Normalize context_hints: trim keys/values; disallow empty keys/values.
        If v isn't a dict[str, str], let Pydantic's type checking raise.
        """
        if v is None:
            return None
        if isinstance(v, dict):
            cleaned: dict[str, str] = {}
            for k, val in v.items():
                ks = k.strip() if isinstance(k, str) else k
                vs = val.strip() if isinstance(val, str) else val
                if not isinstance(ks, str) or not isinstance(vs, str):
                    return v  # let Pydantic raise on type mismatch
                if not ks or not vs:
                    raise ValueError(MSG_ERROR_EMPTY_STRING.format(field="context_hints"))
                cleaned[ks] = vs
            return cleaned
        return v  # let Pydantic raise on type mismatch

    @field_validator("openai", mode="before")
    @classmethod
    def _coerce_openai(cls, v: object) -> object:
        """
        Accept either an OpenAIConfig instance or a mapping to construct one.
        Returns the original value for Pydantic to type-check if unsupported.
        """
        if v is None or isinstance(v, OpenAIConfig):
            return v
        if isinstance(v, Mapping):
            # coerce mapping (e.g., dict) into OpenAIConfig
            return OpenAIConfig(**dict(v))
        return v  # let Pydantic raise on type mismatch


@dataclass
class RetryContext:
    """
    Mutable context passed through adaptive LLM retries to track best candidates.
    """

    messages: list[ChatCompletionMessageParam]
    best_score: float
    best_valid_score: float
    best_fields: dict[str, Any] | None
    best_valid_item: ScrapedItem | None
    all_fields: dict[str, Any]
    has_done_discovery: bool = False


class WorkerPoolConfig(BaseModel):
    """
    Configuration for running a concurrent scraping worker pool.
    """

    take_screenshot: bool
    openai: OpenAIConfig | None = None
    concurrency: int = Field(default=10, ge=1)
    max_queue_size: int | None = Field(default=None)
    on_item_processed: Callable[[object], None] | None = None
    on_error: Callable[[str, Exception], None] | None = None
    on_progress: Callable[[int, int], None] | None = None
    preserve_order: bool = False
    should_cancel: Callable[[], bool] | None = None

    @field_validator("max_queue_size")
    @classmethod
    def _non_negative(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if v < 0:
            raise ValueError(MSG_ERROR_INVALID_LIMIT.format(value=v, min=0, max=10_000_000))
        return v

    model_config = {
        "arbitrary_types_allowed": True,
    }
