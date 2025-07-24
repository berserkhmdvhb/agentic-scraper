import logging
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agentic_scraper.backend.config.constants import IMPORTANT_FIELDS
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_MISSING_IMPORTANT_FIELDS,
    MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL,
    MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL,
    MSG_INFO_ADAPTIVE_EXTRACTION_SUCCESS_WITH_URL,
    MSG_WARN_ADAPTIVE_EXTRACTION_FAILED_AFTER_RETRIES,
)
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.agent.agent_helpers import (
    capture_optional_screenshot,
    extract_context_hints,
    log_structured_data,
    parse_llm_response,
)
from agentic_scraper.backend.scraper.agent.field_utils import (
    get_required_fields,
    normalize_keys,
    score_fields,
)
from agentic_scraper.backend.scraper.agent.prompt_helpers import build_enhanced_prompt
from agentic_scraper.backend.scraper.models import ScrapedItem

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

logger = logging.getLogger(__name__)


async def run_llm_with_retries(
    client: AsyncOpenAI,
    messages: list["ChatCompletionMessageParam"],
    settings: Settings,
    url: str,
) -> str | None:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(settings.retry_attempts),
        wait=wait_exponential(
            multiplier=1, min=settings.retry_backoff_min, max=settings.retry_backoff_max
        ),
        retry=retry_if_exception_type(OpenAIError),
        reraise=True,
    ):
        with attempt:
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
            content = response.choices[0].message.content
            if not content:
                logger.warning(MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL.format(url=url))
                return None
            return content
    return None


async def process_llm_output(
    content: str,
    url: str,
    *,
    take_screenshot: bool,
    settings: Settings,
    cumulative_fields: dict[str, Any],
) -> tuple[ScrapedItem | None, str, set[str]]:
    raw_data = parse_llm_response(content, url, settings)
    if raw_data is None:
        return None, "", set()

    raw_data = normalize_keys(raw_data)
    raw_data["url"] = url

    for k, v in raw_data.items():
        if k not in cumulative_fields:
            cumulative_fields[k] = v

    if take_screenshot:
        screenshot_path = await capture_optional_screenshot(url=url, settings=settings)
        if screenshot_path:
            cumulative_fields["screenshot_path"] = screenshot_path

    try:
        item = ScrapedItem.model_validate(cumulative_fields)
    except ValidationError as ve:
        logger.warning(MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL.format(url=url, exc=ve))
        return None, raw_data.get("page_type", ""), set(raw_data.keys())

    logger.info(MSG_INFO_ADAPTIVE_EXTRACTION_SUCCESS_WITH_URL.format(url=url))
    log_structured_data(item.model_dump(mode="json"), settings=settings)
    return item, raw_data.get("page_type", ""), set(raw_data.keys())


async def extract_adaptive_data(
    text: str,
    url: str,
    *,
    context_hints: dict[str, str] | None = None,
    take_screenshot: bool = False,
    settings: Settings,
) -> ScrapedItem | None:
    if context_hints is None:
        context_hints = extract_context_hints(text, url)

    prompt = build_enhanced_prompt(text, url, context_hints)
    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": prompt}]

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        project=settings.openai_project_id,
    )

    cumulative_fields: dict[str, Any] = {}
    best_score = 0
    best_fields: dict[str, Any] | None = None

    for _ in range(settings.retry_attempts):
        content = await run_llm_with_retries(client, messages, settings, url)
        if content is None:
            return None

        item, page_type, observed_fields = await process_llm_output(
            content=content,
            url=url,
            take_screenshot=take_screenshot,
            settings=settings,
            cumulative_fields=cumulative_fields,
        )

        if item is not None:
            return item

        required = get_required_fields(page_type) or IMPORTANT_FIELDS
        missing = required - observed_fields

        if missing:
            logger.debug(
                MSG_DEBUG_MISSING_IMPORTANT_FIELDS.format(fields=", ".join(sorted(missing)))
            )
            messages[:] = messages[:1]
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Some important fields were missing: {', '.join(sorted(missing))}. "
                        "Please re-analyze the content and "
                        "extract the missing fields if they are present."
                    ),
                }
            )

        # Score based on fields extracted in this attempt
        score = score_fields(observed_fields)
        if score > best_score:
            best_score = score
            best_fields = dict(cumulative_fields)

    if best_fields:
        try:
            item = ScrapedItem.model_validate(best_fields)
        except ValidationError:
            pass
        else:
            logger.info(...)
            return item

    logger.warning(
        MSG_WARN_ADAPTIVE_EXTRACTION_FAILED_AFTER_RETRIES.format(
            attempts=settings.retry_attempts,
            url=url,
        )
    )
    return None
