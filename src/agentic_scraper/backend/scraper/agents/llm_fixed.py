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
# OpenAI client import with safe fallback
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# OpenAI client import with safe fallback (single assignment for mypy)
# -----------------------------------------------------------------------------
try:  # pragma: no cover (import-path dependent)
    from openai import AsyncOpenAI as _ImportedAsyncOpenAI

    _AsyncOpenAI_cls: type = _ImportedAsyncOpenAI
except ImportError:  # pragma: no cover

    class _AsyncOpenAIStub:
        """Minimal stub that mimics `openai.AsyncOpenAI` enough for our usage and tests."""

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
    """
    retry_on = (OpenAIErrorT, APIErrorT, RateLimitErrorT)

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

    return None


async def _extract_impl(
    *,
    request: ScrapeRequest,
    settings: Settings,
) -> ScrapedItem | None:
    """
    Core extraction implementation using fixed system prompt and schema validation.
    """
    # Use a dict-based message shape to satisfy both the real client and the stub.
    messages: list[dict[str, object]] = [
        {"role": "system", "content": MSG_SYSTEM_PROMPT},
        {"role": "user", "content": request.text[:4000]},
    ]

    api_key, project_id = retrieve_openai_credentials(request.openai)
    client = AsyncOpenAI(api_key=api_key, project=project_id)

    try:
        # Both the real SDK and the stub expose: client.chat.completions.create(...)
        response: Any = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        content = response.choices[0].message.content
        if content is None:
            logger.warning(MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL.format(url=request.url))
            return None

        raw_data = parse_llm_response(content, request.url, settings)
        if raw_data is None:
            return None

        if request.take_screenshot:
            screenshot = await capture_optional_screenshot(request.url, settings)
            if screenshot:
                raw_data["screenshot_path"] = screenshot

        try:
            item = ScrapedItem.model_validate({**raw_data, "url": request.url})
        except ValidationError as ve:
            logger.warning(MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL.format(url=request.url, exc=ve))
            return None
    except (RateLimitErrorT, APIErrorT, OpenAIErrorT) as e:
        handle_openai_exception(e, url=request.url, settings=settings)
        return None
    else:
        log_structured_data(item.model_dump(mode="json"), settings=settings)
        logger.info(MSG_INFO_EXTRACTION_SUCCESS_WITH_URL.format(url=request.url))
        return item
