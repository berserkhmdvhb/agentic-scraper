import json
import logging
from typing import TYPE_CHECKING

from openai import APIError, AsyncOpenAI, OpenAIError, RateLimitError
from pydantic import ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_JSON_DECODING_FAILED_WITH_URL,
    MSG_ERROR_LLM_JSON_DECODE_LOG,
    MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL,
    MSG_INFO_EXTRACTION_SUCCESS_WITH_URL,
)
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.agent.agent_helpers import (
    capture_optional_screenshot,
    handle_openai_exception,
    log_structured_data,
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
    prompt = f"""
You are a smart web content extraction agent.

Analyze the content of the page provided below and return a structured JSON object
containing the most relevant information.

You must:
- Infer the page type (e.g. blog, product, job ad, article).
- Extract appropriate fields based on that type.
- Only include fields that are **explicitly present** in the text.
- Return **valid JSON only**, no markdown or explanation.

Common fields per type include:
- Blog: title, author, date, tags, summary
- Product: title, price, brand, availability, features
- Job ad: job_title, company, location, salary, requirements
- Article: headline, author, published_date, summary, tags

Always include:
- url: the original URL of the page
- page_type: a short label for the type of page (e.g. "product", "blog")

Page URL: {url}

Page Content:
{text[:4000]}
""".strip()

    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": prompt}]

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

        content = response.choices[0].message.content
        if not content:
            logger.warning(MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL, url)
            return None

        try:
            raw_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(MSG_ERROR_JSON_DECODING_FAILED_WITH_URL, e, url)
            if settings.is_verbose_mode:
                logger.debug(MSG_ERROR_LLM_JSON_DECODE_LOG.format(e, url))
            return None

        raw_data["url"] = url
        if take_screenshot:
            screenshot_path = await capture_optional_screenshot(
                url=url,
                settings=settings,
            )
            if screenshot_path:
                raw_data["screenshot_path"] = screenshot_path

        try:
            item = ScrapedItem.model_validate(raw_data)
        except ValidationError as ve:
            message = "Failed to validate LLM response for %s: %s", url, ve
            logger.warning(message)
            return None
        else:
            log_structured_data(item.model_dump(mode="json"), settings=settings)
            logger.info(MSG_INFO_EXTRACTION_SUCCESS_WITH_URL, url)
            return item

    except (RateLimitError, APIError, OpenAIError) as e:
        handle_openai_exception(e, url=url, settings=settings)
        return None
