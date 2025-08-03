"""
Fixed-schema LLM extraction agent using a system prompt.

This agent sends HTML content to OpenAI using a predefined system prompt that requests
a consistent set of fields (title, description, price, author, date_published). It performs
a single pass with retry logic and optional screenshot capture.

Use this agent when the output schema is known in advance and doesn't require dynamic adaptation.

Primary entrypoint:
    - extract_structured_data(request, settings)
"""

import logging
from typing import TYPE_CHECKING

from openai import APIError, AsyncOpenAI, OpenAIError, RateLimitError
from pydantic import ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agentic_scraper.backend.scraper.agent.agent_helpers import (
    capture_optional_screenshot,
    handle_openai_exception,
    log_structured_data,
    parse_llm_response,
    retrieve_openai_credentials,
)
from agentic_scraper.config.messages import (
    MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL,
    MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL,
    MSG_INFO_EXTRACTION_SUCCESS_WITH_URL,
    MSG_SYSTEM_PROMPT,
)
from agentic_scraper.config.models import ScrapedItem, ScrapeRequest
from agentic_scraper.core.settings import Settings

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
    Run fixed-schema OpenAI extraction with retry logic and optional screenshot capture.

    This function sends the provided page content to an LLM using a consistent system prompt,
    parses the JSON result, optionally captures a screenshot, and validates the structured data.

    Args:
        request (ScrapeRequest): Encapsulated request parameters including text, URL,
            screenshot preference, and OpenAI credentials.
        settings (Settings): Runtime settings including retry limits, model choice, etc.

    Returns:
        ScrapedItem | None: A structured, validated result object, or None if extraction failed.

    Raises:
        None: OpenAI-related errors are caught and logged internally.
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
            return await _extract_impl(
                request=request,
                settings=settings,
            )
    return None


async def _extract_impl(
    *,
    request: ScrapeRequest,
    settings: Settings,
) -> ScrapedItem | None:
    """
    Core extraction implementation using fixed system prompt and schema validation.

    Sends a prompt to the OpenAI API, parses the response, validates it against
    the ScrapedItem schema, and optionally attaches a screenshot path.

    Args:
        request (ScrapeRequest):
            Input data including cleaned text, URL, screenshot toggle, and credentials.
        settings (Settings): Global runtime settings for LLM interaction.

    Returns:
        ScrapedItem | None: Validated structured item, or None on error.

    Raises:
        None: All exceptions are handled internally and result in None.
    """
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": MSG_SYSTEM_PROMPT},
        {"role": "user", "content": request.text[:4000]},
    ]

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
        else:
            log_structured_data(item.model_dump(mode="json"), settings=settings)
            logger.info(MSG_INFO_EXTRACTION_SUCCESS_WITH_URL.format(url=request.url))
            return item

    except (RateLimitError, APIError, OpenAIError) as e:
        handle_openai_exception(e, url=request.url, settings=settings)

    return None
