import json
import logging
from typing import TYPE_CHECKING

from openai import APIError, AsyncOpenAI, OpenAIError, RateLimitError
from pydantic import HttpUrl
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_API_EXCEPTION,
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
    MSG_SYSTEM_PROMPT,
)
from agentic_scraper.backend.core.settings import load_settings
from agentic_scraper.backend.scraper.models import ScrapedItem

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

settings = load_settings()
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
    Use an LLM to extract structured data from raw page text.

    Args:
        text (str): Cleaned text content extracted from the webpage.
        url (str): Source URL of the page (included in returned schema).

    Returns:
        ScrapedItem: Pydantic model with structured data.

    Raises:
        ValueError: If LLM output is not valid JSON or schema is malformed.
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
            logger.exception(MSG_ERROR_LLM_RESPONSE_MALFORMED, response)
            raise ValueError(MSG_ERROR_MISSING_LLM_CONTENT) from e

        if content is None:
            logger.exception(MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT, response)
            raise ValueError(MSG_ERROR_MISSING_LLM_CONTENT)

        try:
            raw_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.exception(MSG_ERROR_LLM_JSON_DECODE_LOG, content)
            raise ValueError(MSG_ERROR_JSON_DECODING_FAILED.format(error=e)) from e

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
