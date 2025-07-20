import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from openai import APIError, AsyncOpenAI, OpenAIError, RateLimitError
from pydantic import HttpUrl
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_API_EXCEPTION,
    MSG_DEBUG_PARSED_STRUCTURED_DATA,
    MSG_ERROR_API,
    MSG_ERROR_API_LOG,
    MSG_ERROR_JSON_DECODING_FAILED,
    MSG_ERROR_LLM_JSON_DECODE_LOG,
    MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT,
    MSG_ERROR_LLM_RESPONSE_MALFORMED,
    MSG_ERROR_MISSING_LLM_CONTENT,
    MSG_ERROR_OPENAI_UNEXPECTED,
    MSG_ERROR_OPENAI_UNEXPECTED_LOG,
    MSG_ERROR_RATE_LIMIT,
    MSG_ERROR_RATE_LIMIT_LOG,
    MSG_ERROR_SCREENSHOT_FAILED,
    MSG_SYSTEM_PROMPT,
)
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.backend.scraper.screenshotter import capture_screenshot

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

settings = get_settings()
logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=settings.openai_api_key, project=settings.openai_project_id)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OpenAIError),
    reraise=True,
)
async def extract_structured_data(text: str, url: str) -> ScrapedItem:
    """
    Extract structured data from a page's text using a language model,
    and optionally capture a screenshot of the source URL.

    This function sends a prompt to the OpenAI API to extract structured
    fields (e.g., title, price, author) from the provided page content.
    It then attempts to capture a full-page screenshot of the URL and
    attach the screenshot path to the resulting data model.

    The function includes retry logic to handle transient OpenAI API errors.

    Args:
        text (str): Cleaned main content of the web page to be analyzed.
        url (str): The original URL of the web page (used for metadata and screenshot).

    Returns:
        ScrapedItem: A validated data model with extracted fields and optional screenshot path.

    Raises:
        ValueError: If the model response is empty, malformed, non-JSON, or if API errors occur.
    """

    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": MSG_SYSTEM_PROMPT},
        {"role": "user", "content": text[:4000]},
    ]

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        try:
            content = response.choices[0].message.content
        except (IndexError, AttributeError) as e:
            logger.exception(MSG_ERROR_LLM_RESPONSE_MALFORMED)
            raise ValueError(MSG_ERROR_MISSING_LLM_CONTENT) from e

        if content is None:
            logger.error(MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT)
            raise ValueError(MSG_ERROR_MISSING_LLM_CONTENT)

        try:
            raw_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.exception(MSG_ERROR_LLM_JSON_DECODE_LOG)
            raise ValueError(MSG_ERROR_JSON_DECODING_FAILED.format(error=e)) from e

        try:
            screenshot = await capture_screenshot(url, output_dir=Path(settings.screenshot_dir))
            raw_data["screenshot_path"] = screenshot
        except Exception:
            logger.exception(MSG_ERROR_SCREENSHOT_FAILED)

        logger.debug(MSG_DEBUG_PARSED_STRUCTURED_DATA, raw_data)
        return ScrapedItem(url=HttpUrl(url), **raw_data)

    except RateLimitError as e:
        logger.exception(MSG_ERROR_RATE_LIMIT_LOG)
        raise ValueError(MSG_ERROR_RATE_LIMIT) from e

    except APIError as e:
        logger.exception(MSG_ERROR_API_LOG)
        logger.debug(MSG_DEBUG_API_EXCEPTION, exc_info=True)
        raise ValueError(MSG_ERROR_API.format(error=e)) from e

    except OpenAIError as e:
        logger.exception(MSG_ERROR_OPENAI_UNEXPECTED_LOG)
        raise ValueError(MSG_ERROR_OPENAI_UNEXPECTED.format(error=e)) from e
