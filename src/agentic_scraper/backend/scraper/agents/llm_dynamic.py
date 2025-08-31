# src/agentic_scraper/backend/scraper/agents/llm_dynamic.py
"""
Dynamic LLM-based extraction agent for single-pass structured data scraping.

This agent uses a flexible prompt template to extract structured data from
webpage content using OpenAI's Chat API. It performs a single pass with
configurable retry logic for transient API failures. The agent supports optional
screenshot capture and key normalization.

Primary entrypoint:
    - extract_structured_data(request, settings)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agentic_scraper.backend.config.aliases import APIErrorT, OpenAIErrorT, RateLimitErrorT
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_LLM_PROMPT_WITH_URL,
    MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL,
    MSG_INFO_FIELD_DISCOVERY_SCORE,
    MSG_OPENAI_CLIENT_UNAVAILABLE,
)
from agentic_scraper.backend.scraper.agents.agent_helpers import (
    capture_optional_screenshot,
    handle_openai_exception,
    parse_llm_response,
    retrieve_openai_credentials,
    try_validate_scraped_item,
)
from agentic_scraper.backend.scraper.agents.field_utils import (
    detect_unavailable_fields,
    normalize_fields,
    normalize_keys,
    score_nonempty_fields,
)
from agentic_scraper.backend.scraper.agents.prompt_helpers import build_prompt

if TYPE_CHECKING:
    from agentic_scraper.backend.core.settings import Settings
    from agentic_scraper.backend.scraper.models import ScrapeRequest
    from agentic_scraper.backend.scraper.schemas import ScrapedItem

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
                    # Mirrors llm_fixed stub behavior with a clear message constant
                    msg = MSG_OPENAI_CLIENT_UNAVAILABLE
                    raise RuntimeError(msg)

    _AsyncOpenAI_cls = _AsyncOpenAIStub

# Bind the public name exactly once so mypy doesn't see a redefinition.
AsyncOpenAI: type = _AsyncOpenAI_cls


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


async def extract_structured_data(
    request: ScrapeRequest,
    *,
    settings: Settings,
) -> ScrapedItem | None:
    """
    LLM-based structured data extraction using a dynamic prompt and retry logic.
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
    Core logic for extracting structured data from page content using OpenAI's Chat API.
    """
    prompt = build_prompt(
        text=request.text,
        url=request.url,
        prompt_style="enhanced",
        context_hints=request.context_hints,
    )
    logger.debug(MSG_DEBUG_LLM_PROMPT_WITH_URL.format(url=request.url, prompt=prompt))

    # Use a dict-based message shape to satisfy both the real client and the stub.
    messages_payload: list[dict[str, object]] = [{"role": "user", "content": prompt}]
    api_key, project_id = retrieve_openai_credentials(request.openai)
    client = AsyncOpenAI(api_key=api_key, project=project_id)

    try:
        # Both the real SDK and the stub expose: client.chat.completions.create(...)
        response: Any = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages_payload,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        content = response.choices[0].message.content
        if not content:
            logger.warning(MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL.format(url=request.url))
            return None

        # Parse and normalize
        raw_data = parse_llm_response(content, request.url, settings)
        if raw_data is None:
            return None

        raw_data = normalize_keys(raw_data)
        raw_data["url"] = request.url

        unavailable_fields = detect_unavailable_fields(raw_data)
        score = score_nonempty_fields(raw_data)
        logger.info(
            MSG_INFO_FIELD_DISCOVERY_SCORE.format(
                url=request.url,
                score=score,
                num_unavailable=len(unavailable_fields),
            )
        )

        normalized = normalize_fields(raw_data)

        # Optional screenshot
        if request.take_screenshot:
            screenshot_path = await capture_optional_screenshot(request.url, settings)
            if screenshot_path:
                normalized.setdefault("screenshot_path", screenshot_path)

        return try_validate_scraped_item(normalized, request.url, settings)

    except (RateLimitErrorT, APIErrorT, OpenAIErrorT) as e:
        handle_openai_exception(e, url=request.url, settings=settings)
        return None
