import logging
from typing import TYPE_CHECKING

from openai import APIError, AsyncOpenAI, OpenAIError, RateLimitError
from pydantic import ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL,
    MSG_ERROR_LLM_RESPONSE_MALFORMED_WITH_URL,
    MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL,
    MSG_INFO_EXTRACTION_SUCCESS_WITH_URL,
    MSG_SYSTEM_PROMPT,
)
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.agent.agent_helpers import (
    capture_optional_screenshot,
    handle_openai_exception,
    log_structured_data,
    parse_llm_response,
)
from agentic_scraper.backend.scraper.models import ScrapedItem

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

logger = logging.getLogger(__name__)


async def extract_structured_data(
    text: str,
    url: str,
    *,
    take_screenshot: bool = False,
    settings: Settings,
) -> ScrapedItem | None:
    """
    Run OpenAI + optional screenshot capture with retry behavior driven by Settings.
    """
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(settings.retry_attempts),
        wait=wait_exponential(
            multiplier=1, min=settings.retry_backoff_min, max=settings.retry_backoff_max
        ),
        retry=retry_if_exception_type(OpenAIError),
        reraise=True,
    ):
        with attempt:
            return await _extract_impl(
                text, url, take_screenshot=take_screenshot, settings=settings
            )

    return None


async def _extract_impl(
    text: str,
    url: str,
    *,
    take_screenshot: bool,
    settings: Settings,
) -> ScrapedItem | None:
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": MSG_SYSTEM_PROMPT},
        {"role": "user", "content": text[:4000]},
    ]

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        project=settings.openai_project_id,
    )

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        try:
            content = response.choices[0].message.content
        except (IndexError, AttributeError):
            logger.warning(MSG_ERROR_LLM_RESPONSE_MALFORMED_WITH_URL, url)
            return None

        if content is None:
            logger.warning(MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL, url)
            return None

        raw_data = parse_llm_response(content, url, settings)
        if raw_data is None:
            return None

        if take_screenshot:
            screenshot = await capture_optional_screenshot(url, settings)
            if screenshot:
                raw_data["screenshot_path"] = screenshot

        try:
            item = ScrapedItem.model_validate({**raw_data, "url": url})
        except ValidationError as ve:
            logger.warning(MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL, url, ve)
            return None
        else:
            log_structured_data(item.model_dump(mode="json"), settings=settings)
            logger.info(MSG_INFO_EXTRACTION_SUCCESS_WITH_URL, url)
            return item

    except (RateLimitError, APIError, OpenAIError) as e:
        handle_openai_exception(e, url, settings)

    return None
