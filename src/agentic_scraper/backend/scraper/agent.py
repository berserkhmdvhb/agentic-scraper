import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from openai import APIError, AsyncOpenAI, OpenAIError, RateLimitError
from playwright.async_api import Error as PlaywrightError
from pydantic import HttpUrl
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_API_EXCEPTION,
    MSG_DEBUG_PARSED_STRUCTURED_DATA,
    MSG_ERROR_API,
    MSG_ERROR_API_LOG_WITH_URL,
    MSG_ERROR_JSON_DECODING_FAILED_WITH_URL,
    MSG_ERROR_LLM_JSON_DECODE_LOG,
    MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL,
    MSG_ERROR_LLM_RESPONSE_MALFORMED_WITH_URL,
    MSG_ERROR_OPENAI_UNEXPECTED,
    MSG_ERROR_OPENAI_UNEXPECTED_LOG_WITH_URL,
    MSG_ERROR_RATE_LIMIT_DETAIL,
    MSG_ERROR_RATE_LIMIT_LOG_WITH_URL,
    MSG_ERROR_SCREENSHOT_FAILED_WITH_URL,
    MSG_SYSTEM_PROMPT,
)
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.backend.scraper.screenshotter import capture_screenshot

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

        try:
            raw_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(MSG_ERROR_JSON_DECODING_FAILED_WITH_URL, e, url)
            logger.debug(MSG_ERROR_LLM_JSON_DECODE_LOG.format(e, url))
            return None

        if take_screenshot:
            try:
                screenshot = await capture_screenshot(url, output_dir=Path(settings.screenshot_dir))
                raw_data["screenshot_path"] = screenshot
            except (PlaywrightError, OSError, ValueError):
                logger.warning(MSG_ERROR_SCREENSHOT_FAILED_WITH_URL, url)

        logger.debug(MSG_DEBUG_PARSED_STRUCTURED_DATA, raw_data)
        return ScrapedItem(url=HttpUrl(url), **raw_data)

    except RateLimitError as e:
        logger.warning(MSG_ERROR_RATE_LIMIT_LOG_WITH_URL, url)
        logger.debug(MSG_ERROR_RATE_LIMIT_DETAIL, e)

    except APIError as e:
        logger.warning(MSG_ERROR_API_LOG_WITH_URL, url)
        logger.debug(MSG_DEBUG_API_EXCEPTION, exc_info=True)
        logger.debug(MSG_ERROR_API.format(error=e))

    except OpenAIError as e:
        logger.warning(MSG_ERROR_OPENAI_UNEXPECTED_LOG_WITH_URL, url)
        logger.debug(MSG_ERROR_OPENAI_UNEXPECTED.format(error=e))

    return None
