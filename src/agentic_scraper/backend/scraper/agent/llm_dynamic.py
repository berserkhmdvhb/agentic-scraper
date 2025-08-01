import logging
from typing import TYPE_CHECKING

from openai import APIError, AsyncOpenAI, OpenAIError, RateLimitError
from pydantic import ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL,
    MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL,
    MSG_INFO_EXTRACTION_SUCCESS_WITH_URL,
)
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.agent.agent_helpers import (
    capture_optional_screenshot,
    handle_openai_exception,
    log_structured_data,
    parse_llm_response,
)
from agentic_scraper.backend.scraper.agent.prompt_helpers import build_prompt
from agentic_scraper.backend.scraper.models import ScrapedItem, ScrapeRequest

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

logger = logging.getLogger(__name__)


async def extract_structured_data(
    request: ScrapeRequest,
    *,
    settings: Settings,
) -> ScrapedItem | None:
    """
    LLM-based structured data extraction using a dynamic prompt and retry logic.

    Args:
        request (ScrapeRequest): Contains page text, URL, OpenAI credentials, and screenshot flag.
        settings (Settings): Retry, token, and model configuration.

    Returns:
        ScrapedItem | None: Validated structured data or None on failure.
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
    Core LLM extraction logic using a prompt template and OpenAI completion API.

    Args:
        request (ScrapeRequest): Encapsulated scraping input and credentials.
        settings (Settings): Application-wide configuration.

    Returns:
        ScrapedItem | None: Parsed and validated data or None on failure.
    """
    prompt = build_prompt(
        text=request.text,
        url=request.url,
        prompt_style="simple",
    )

    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": prompt}]
    client = AsyncOpenAI(
        api_key=request.openai.api_key,
        project=request.openai.project_id,
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

        raw_data = parse_llm_response(content, request.url, settings)
        if raw_data is None:
            return None

        raw_data["url"] = request.url

        if request.take_screenshot:
            screenshot_path = await capture_optional_screenshot(
                url=request.url,
                settings=settings,
            )
            if screenshot_path:
                raw_data["screenshot_path"] = screenshot_path

        try:
            item = ScrapedItem.model_validate(raw_data)
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
