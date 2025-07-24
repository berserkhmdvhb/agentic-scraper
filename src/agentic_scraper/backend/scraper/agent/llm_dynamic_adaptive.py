import asyncio
import logging
import re
from typing import Any

from openai import AsyncOpenAI, OpenAIError
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from agentic_scraper.backend.config.constants import IMPORTANT_FIELDS
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_LLM_RETRY_ATTEMPT,
    MSG_DEBUG_MISSING_IMPORTANT_FIELDS,
    MSG_DEBUG_USING_BEST_CANDIDATE_FIELDS,
    MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL,
    MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL,
    MSG_INFO_ADAPTIVE_EXTRACTION_SUCCESS_WITH_URL,
    MSG_WARN_ADAPTIVE_EXTRACTION_FAILED_AFTER_RETRIES,
    MSG_WARN_LLM_RATE_LIMIT_SLEEP,
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

logger = logging.getLogger(__name__)


RATE_LIMIT_RETRY_REGEX = re.compile(r"try again in ([\d.]+)s", re.IGNORECASE)


async def run_llm_with_retries(
    client: AsyncOpenAI,
    messages: list[ChatCompletionMessageParam],
    settings: Settings,
    url: str,
) -> str | None:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(settings.retry_attempts),
        wait=wait_random_exponential(
            multiplier=1, min=settings.retry_backoff_min, max=settings.retry_backoff_max
        ),
        retry=retry_if_exception_type(OpenAIError),
        reraise=True,
    ):
        with attempt:
            try:
                response = await client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                )
                if not response.choices or not response.choices[0].message.content:
                    logger.warning(MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL.format(url=url))
                    return None
                return response.choices[0].message.content.strip()

            except OpenAIError as e:
                # Smart rate-limit handler
                message = getattr(e, "message", "") or str(e)
                if "rate_limit_exceeded" in message:
                    match = RATE_LIMIT_RETRY_REGEX.search(message)
                    if match:
                        delay = float(match.group(1))
                        logger.warning(MSG_WARN_LLM_RATE_LIMIT_SLEEP.format(url=url, delay=delay))
                        await asyncio.sleep(delay)
                # Let tenacity handle retries
                raise

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

    for attempt_num in range(1, settings.llm_schema_retries + 1):
        logger.debug(
            MSG_DEBUG_LLM_RETRY_ATTEMPT.format(
                attempt=attempt_num,
                total=settings.llm_schema_retries,
                url=url,
            )
        )
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
            # Keep only the original prompt, discard previous retry instructions
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

        # Score based on this round's observed fields (not cumulative)
        score = score_fields(observed_fields)
        if score > best_score:
            best_score = score
            best_fields = dict(cumulative_fields)

    if best_fields:
        logger.debug(MSG_DEBUG_USING_BEST_CANDIDATE_FIELDS.format(fields=list(best_fields.keys())))
        try:
            item = ScrapedItem.model_validate(best_fields)
        except ValidationError:
            pass
        else:
            logger.info(MSG_INFO_ADAPTIVE_EXTRACTION_SUCCESS_WITH_URL.format(url=url))
            return item

    logger.warning(
        MSG_WARN_ADAPTIVE_EXTRACTION_FAILED_AFTER_RETRIES.format(
            attempts=settings.llm_schema_retries,
            url=url,
        )
    )
    return None
