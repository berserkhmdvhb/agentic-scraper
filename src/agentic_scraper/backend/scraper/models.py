"""
Internal request/worker models for the scraper pipeline.

Responsibilities:
- Define the per-URL request payload shape passed from fetch/prepare to agents.
- Capture retry/adaptation context for LLM-driven extraction strategies.
- Configure the concurrent worker pool that orchestrates scraping.

Models:
- `ScrapeRequest`: Normalized per-page input (text, url, OpenAI config, hints).
- `RetryContext`: Mutable state shared across adaptive LLM retries.
- `WorkerPoolConfig`: Tuning knobs and hooks for the scraping worker pool.

Serialization:
- Pydantic models (`BaseModel`) validate/normalize inputs (e.g., URL, empty strings).
- `OpenAIConfig` can be provided directly or as a dict (coerced in a validator).

Usage:
    from agentic_scraper.backend.scraper.models import ScrapeRequest, WorkerPoolConfig

    req = ScrapeRequest(text=html_text, url="https://example.com", take_screenshot=True)
    pool = WorkerPoolConfig(take_screenshot=True, concurrency=8)

Notes:
- These models are internal to the scraper layer; they do not perform any I/O.
- Keep validators light-weight and deterministic — they run in hot paths.
"""

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

__all__ = ["RetryContext", "ScrapeRequest", "WorkerPoolConfig"]


class ScrapeRequest(BaseModel):
    """
    Per-URL scrape input prepared by the fetch/prepare stage.

    Attributes:
        text (str): Main visible text content for the page (already extracted).
        url (str): Page URL (validated to be http/https; trimmed).
        take_screenshot (bool): Whether a screenshot should be captured downstream.
        openai (OpenAIConfig | None): Per-request OpenAI credentials (optional).
        context_hints (dict[str, str] | None): Key-value hints for agents (trimmed; no empties).

    Notes:
        - URL is kept as a `str` internally for frictionless use across agents/helpers.
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
        """Ensure URL is http(s), trimmed, and syntactically valid."""
        return validate_url(v)

    @field_validator("text", mode="before")
    @classmethod
    def _validate_text(cls, v: str) -> str:
        """Reject missing/blank text; trim surrounding whitespace."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError(MSG_ERROR_EMPTY_STRING.format(field="text"))
        return v.strip()

    @field_validator("context_hints", mode="before")
    @classmethod
    def _clean_context_hints(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """
        Normalize `context_hints`: trim keys/values; disallow empty keys/values.

        If `v` isn't `dict[str, str]`, let Pydantic's type checking raise.
        """
        if v is None:
            return None
        if isinstance(v, dict):
            cleaned: dict[str, str] = {}
            for k, val in v.items():
                ks = k.strip() if isinstance(k, str) else k
                vs = val.strip() if isinstance(val, str) else val
                if not isinstance(ks, str) or not isinstance(vs, str):
                    # Let Pydantic enforce typing (keeps behavior unchanged).
                    return v
                if not ks or not vs:
                    raise ValueError(MSG_ERROR_EMPTY_STRING.format(field="context_hints"))
                cleaned[ks] = vs
            return cleaned
        # Non-dict inputs fall through to Pydantic's own error handling.
        return v

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
            # Coerce mapping (e.g., plain dict) into OpenAIConfig without changing behavior.
            return OpenAIConfig(**dict(v))
        return v  # Let Pydantic raise on type mismatch


@dataclass
class RetryContext:
    """
    Mutable context passed through adaptive LLM retries to track best candidates.

    Attributes:
        messages (list[ChatCompletionMessageParam]): Prompt/response history.
        best_score (float): Highest overall score observed so far (any candidate).
        best_valid_score (float): Highest score among candidates that validate.
        best_fields (dict[str, Any] | None): Raw fields from the best-scoring candidate.
        best_valid_item (ScrapedItem | None): Parsed/validated item for the best valid candidate.
        all_fields (dict[str, Any]): Aggregated field observations (debug/telemetry).
        has_done_discovery (bool): Whether discovery prompts have been executed.
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

    Attributes:
        take_screenshot (bool): Whether to capture screenshots for pages.
        openai (OpenAIConfig | None): Credentials for LLM-enabled agents (optional).
        concurrency (int): Number of concurrent workers (>= 1).
        max_queue_size (int | None): Optional queue bound for backpressure (>= 0).
        on_item_processed (Callable[[object], None] | None): Hook per successful item.
        on_error (Callable[[str, Exception], None] | None): Hook on per-URL failure.
        on_progress (Callable[[int, int], None] | None): Hook with (done, total).
        preserve_order (bool): If True, emit results in input order (may reduce throughput).
        should_cancel (Callable[[], bool] | None): Cooperative cancel check for long runs.

    Notes:
        - `arbitrary_types_allowed=True` is enabled to allow callables in the model.
        - This config is consumed by the pipeline/executor layer; no I/O here.
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
        """Ensure `max_queue_size` is None or non-negative."""
        if v is None:
            return None
        if v < 0:
            raise ValueError(MSG_ERROR_INVALID_LIMIT.format(value=v, min=0, max=10_000_000))
        return v

    # Allow callables/types that Pydantic doesn't know about by default.
    model_config = {"arbitrary_types_allowed": True}
