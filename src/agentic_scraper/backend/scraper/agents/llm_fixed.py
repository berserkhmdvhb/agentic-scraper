"""
Fixed-schema LLM extraction agent (OpenAI Chat Completions).

Responsibilities:
- Call an LLM with a stable system prompt (`MSG_SYSTEM_PROMPT`) and user content.
- Parse the model's JSON output, validate against `ScrapedItem`, and enrich with an
  optional screenshot path.
- Apply retry/backoff for transient OpenAI errors.

Public API:
- `extract_structured_data`: Run the fixed-schema extraction with retries.
- (internal) `_extract_impl`: Single-attempt implementation (no retries).

Operational:
- Retries: tenacity with exponential backoff; exception-filtered for OpenAI errors.
- Logging: verbosity-aware; structured messages come from `config.messages`.
- Cancellation: not cooperatively cancellable here (handled at pipeline/worker level).

Usage:
    from agentic_scraper.backend.scraper.agents.llm_fixed import extract_structured_data

    item = await extract_structured_data(request, settings=settings)
    if item:
        print(item.model_dump())

Notes:
- We import `AsyncOpenAI` lazily with a stub fallback for environments where the SDK
  is unavailable (e.g., CI). This keeps import-time failures from breaking tests.
- We deliberately pass dict-shaped messages to work with both the real SDK and the stub.
"""

# src/agentic_scraper/backend/scraper/agents/llm_fixed.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agentic_scraper.backend.config.aliases import APIErrorT, OpenAIErrorT, RateLimitErrorT
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL,
    MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL,
    MSG_ERROR_OPENAI_UNEXPECTED,
    MSG_INFO_EXTRACTION_SUCCESS_WITH_URL,
    MSG_SYSTEM_PROMPT,
)
from agentic_scraper.backend.scraper.agents.agent_helpers import (
    capture_optional_screenshot,
    handle_openai_exception,
    log_structured_data,
    parse_llm_response,
    retrieve_openai_credentials,
)
from agentic_scraper.backend.scraper.schemas import ScrapedItem

if TYPE_CHECKING:
    from agentic_scraper.backend.core.settings import Settings
    from agentic_scraper.backend.scraper.models import ScrapeRequest

logger = logging.getLogger(__name__)

__all__ = ["extract_structured_data"]

# -----------------------------------------------------------------------------
# OpenAI client import with safe fallback (single assignment for mypy)
# -----------------------------------------------------------------------------
try:  # pragma: no cover (import-path dependent)
    from openai import AsyncOpenAI as _ImportedAsyncOpenAI

    _AsyncOpenAI_cls: type = _ImportedAsyncOpenAI
except ImportError:  # pragma: no cover

    class _AsyncOpenAIStub:
        """Minimal stub that mimics `openai.AsyncOpenAI` enough for our usage and tests.

        Notes:
            - We raise a RuntimeError inside `.create(...)` to surface the absence of
              the real SDK when a call is attempted. Importing remains safe.
            - This avoids test environments needing the OpenAI package installed.
        """

        def __init__(self, *, api_key: str | None = None, project: str | None = None) -> None:
            self.api_key = api_key
            self.project = project
            self.chat = self.Chat()

        class Chat:
            def __init__(self) -> None:
                self.completions = self.Completions()

            class Completions:
                @staticmethod
                async def create(
                    *,
                    model: str,
                    messages: list[dict[str, object]],
                    temperature: float,
                    max_tokens: int,
                ) -> object:
                    _ = (model, messages, temperature, max_tokens)
                    # Keep the exact message text (from messages constants) to match logs/tests.
                    msg = MSG_ERROR_OPENAI_UNEXPECTED
                    raise RuntimeError(msg)

    _AsyncOpenAI_cls = _AsyncOpenAIStub

# Bind the public name exactly once so mypy doesn't see a redefinition.
AsyncOpenAI: type = _AsyncOpenAI_cls


async def extract_structured_data(
    request: ScrapeRequest,
    *,
    settings: Settings,
) -> ScrapedItem | None:
    """
    Run fixed-schema OpenAI extraction with retry logic and optional screenshot capture.

    Args:
        request (ScrapeRequest): Prepared input (normalized URL/text, optional creds).
        settings (Settings): Runtime configuration (model name, tokens, temperature, retry policy).

    Returns:
        ScrapedItem | None: Validated item on success; None if parsing/validation fails
            or an OpenAI error occurs (after retries).

    Raises:
        None: All OpenAI-related exceptions are handled via tenacity retries and
            consolidated logging; final errors return None.

    Notes:
        - Retries are limited by `settings.retry_attempts` with exponential backoff,
          bounded by `settings.retry_backoff_min`..`retry_backoff_max`.
        - This function focuses on LLM I/O + validation; pipeline cancellation is handled
          at higher layers (worker/pipeline).
    """
    # Only retry on known OpenAI types (imported as typing aliases).
    retry_on = (OpenAIErrorT, APIErrorT, RateLimitErrorT)

    # Tenacity orchestrates the retry/backoff; we delegate one attempt to _extract_impl.
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(settings.retry_attempts),
        wait=wait_exponential(
            multiplier=1,
            min=settings.retry_backoff_min,
            max=settings.retry_backoff_max,
        ),
        retry=retry_if_exception_type(retry_on),
        reraise=True,
    ):
        with attempt:
            return await _extract_impl(request=request, settings=settings)

    # Defensive: flow should return from within the loop or raise; keep signature strict.
    return None


async def _extract_impl(
    *,
    request: ScrapeRequest,
    settings: Settings,
) -> ScrapedItem | None:
    """
    Single-attempt fixed-schema extraction: call LLM, parse JSON, validate item.

    This is separated from the retry wrapper so the attempt body remains small and
    easier to reason about (and unit test in isolation).

    Args:
        request (ScrapeRequest): Input including `text` (trimmed) and OpenAI config.
        settings (Settings): Runtime configuration.

    Returns:
        ScrapedItem | None: Structured/validated item, or None on parse/validation failure.

    Notes:
        - Messages are plain dicts to satisfy both the real client and the stub.
        - We pass only the first ~4k chars of text to avoid excessive token usage.
        - Screenshot is optional and appended to `raw_data` when requested.
    """
    # Use a dict-based message shape to satisfy both the real client and the stub.
    messages: list[dict[str, object]] = [
        {"role": "system", "content": MSG_SYSTEM_PROMPT},
        {"role": "user", "content": request.text[:4000]},  # trim to control token usage
    ]

    # Extract and validate credentials early; fail fast if missing/invalid.
    api_key, project_id = retrieve_openai_credentials(request.openai)
    client = AsyncOpenAI(api_key=api_key, project=project_id)

    try:
        # Real SDK & stub both expose: client.chat.completions.create(...)
        response: Any = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        # OpenAI SDK shape: choices[0].message.content (string or None)
        content = response.choices[0].message.content
        if content is None:
            # Some model/call failures return empty/None content; warn + bail.
            logger.warning(MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL.format(url=request.url))
            return None

        # Parse JSON (with repair pass) and bail quietly on failure.
        raw_data = parse_llm_response(content, request.url, settings)
        if raw_data is None:
            return None

        # Optional screenshot—deferred until after a successful parse to avoid waste.
        if request.take_screenshot:
            screenshot = await capture_optional_screenshot(request.url, settings)
            if screenshot:
                raw_data["screenshot_path"] = screenshot

        try:
            # Ensure `url` is always present/normalized in the validated item.
            item = ScrapedItem.model_validate({**raw_data, "url": request.url})
        except ValidationError as ve:
            # Log at warning; the caller treats None as "no item" for this URL.
            logger.warning(MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL.format(url=request.url, exc=ve))
            return None
    except (RateLimitErrorT, APIErrorT, OpenAIErrorT) as e:
        # Uniform, verbosity-aware logging for OpenAI exceptions.
        handle_openai_exception(e, url=request.url, settings=settings)
        return None
    else:
        # Best-effort structured log (and optional JSON dump in verbose modes).
        log_structured_data(item.model_dump(mode="json"), settings=settings)
        logger.info(MSG_INFO_EXTRACTION_SUCCESS_WITH_URL.format(url=request.url))
        return item
