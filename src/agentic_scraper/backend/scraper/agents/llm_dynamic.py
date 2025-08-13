"""
Dynamic LLM-based extraction agent for single-pass structured data scraping.

This agent uses a flexible prompt template to extract structured data from
webpage content using OpenAI's Chat API. It performs a single pass with
configurable retry logic for transient API failures. The agent supports optional
screenshot capture and key normalization.

Usage:
    Used when adaptive retries are not necessary, and a single-shot response
    from the LLM is expected to be sufficient.

Primary entrypoint:
    - extract_structured_data(request, settings)
"""

import logging
from typing import TYPE_CHECKING

from openai import APIError, AsyncOpenAI, OpenAIError, RateLimitError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_LLM_PROMPT_WITH_URL,
    MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL,
    MSG_INFO_FIELD_DISCOVERY_SCORE,
)
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.agents.agent_helpers import (
    capture_optional_screenshot,
    handle_openai_exception,
    retrieve_openai_credentials,
    try_validate_scraped_item,
)
from agentic_scraper.backend.scraper.agents.agent_parser import parse_llm_response
from agentic_scraper.backend.scraper.agents.field_utils import (
    detect_unavailable_fields,
    normalize_fields,
    normalize_keys,
    score_nonempty_fields,
)
from agentic_scraper.backend.scraper.agents.prompt_helpers import build_prompt
from agentic_scraper.backend.scraper.models import ScrapeRequest
from agentic_scraper.backend.scraper.schemas import ScrapedItem

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

logger = logging.getLogger(__name__)

__all__ = ["extract_structured_data"]


async def extract_structured_data(
    request: ScrapeRequest,
    *,
    settings: Settings,
) -> ScrapedItem | None:
    """
    LLM-based structured data extraction using a dynamic prompt and retry logic.

    Internally retries the extraction process on transient OpenAI errors
    using exponential backoff. Delegates core extraction logic to `_extract_impl`.

    Args:
        request (ScrapeRequest): Contains page text, URL, OpenAI credentials, and screenshot flag.
        settings (Settings): Retry, token, and model configuration.

    Returns:
        ScrapedItem | None: Validated structured data or None on failure.

    Raises:
        None: All exceptions are internally handled or retried.
    """
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(settings.retry_attempts),
        wait=wait_exponential(
            multiplier=1,
            min=settings.retry_backoff_min,
            max=settings.retry_backoff_max,
        ),
        retry=retry_if_exception_type(OpenAIError),
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

    Builds a dynamic prompt, sends it to the LLM, parses and validates the response,
    and optionally captures a screenshot if enabled.

    Args:
        request (ScrapeRequest): Encapsulated scraping input and credentials.
        settings (Settings): Application-wide configuration.

    Returns:
        ScrapedItem | None: Parsed and validated data or None on failure.

    Raises:
        None: All OpenAI-related exceptions are handled via `handle_openai_exception`.
    """
    prompt = build_prompt(
        text=request.text,
        url=request.url,
        prompt_style="enhanced",
        context_hints=request.context_hints,
    )
    logger.debug(MSG_DEBUG_LLM_PROMPT_WITH_URL.format(url=request.url, prompt=prompt))
    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": prompt}]
    api_key, project_id = retrieve_openai_credentials(request.openai)

    client = AsyncOpenAI(
        api_key=api_key,
        project=project_id,
    )

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        content = response.choices[0].message.content
        if not content:
            logger.warning(MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL.format(url=request.url))
            return None

        # ─── Parse, Normalize, and Score ──────────────────────────────────────
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

        # ─── Screenshot (Optional) ────────────────────────────────────────────
        if request.take_screenshot:
            screenshot_path = await capture_optional_screenshot(request.url, settings)
            if screenshot_path:
                normalized.setdefault("screenshot_path", screenshot_path)

        return try_validate_scraped_item(normalized, request.url, settings)

    except (RateLimitError, APIError, OpenAIError) as e:
        handle_openai_exception(e, url=request.url, settings=settings)
        return None
