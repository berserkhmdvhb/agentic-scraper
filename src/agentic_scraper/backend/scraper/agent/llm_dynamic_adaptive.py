import asyncio
import copy
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
    MSG_DEBUG_FIELD_SCORE_PER_RETRY,
    MSG_DEBUG_LLM_INITIAL_PROMPT,
    MSG_DEBUG_LLM_RETRY_ATTEMPT,
    MSG_DEBUG_LLM_RETRY_PROMPT,
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
from agentic_scraper.backend.scraper.agent.prompt_helpers import (
    build_prompt,
    build_retry_prompt,
)
from agentic_scraper.backend.scraper.models import ScrapedItem, ScrapeRequest

logger = logging.getLogger(__name__)

RATE_LIMIT_RETRY_REGEX = re.compile(r"(?:retry|try again).*?(\d+(?:\.\d+)?)s", re.IGNORECASE)


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
                message = getattr(e, "message", "") or str(e)
                if "rate_limit_exceeded" in message:
                    match = RATE_LIMIT_RETRY_REGEX.search(message)
                    if match:
                        delay = float(match.group(1))
                        logger.warning(MSG_WARN_LLM_RATE_LIMIT_SLEEP.format(url=url, delay=delay))
                        await asyncio.sleep(delay)
                raise

    return None


async def process_llm_output(
    content: str,
    url: str,
    *,
    take_screenshot: bool,
    settings: Settings,
) -> tuple[ScrapedItem | None, str, set[str], dict[str, Any]]:
    raw_data = parse_llm_response(content, url, settings)
    if raw_data is None:
        return None, "", set(), {}

    raw_data = normalize_keys(raw_data)
    raw_data["url"] = url

    if take_screenshot:
        screenshot_path = await capture_optional_screenshot(url=url, settings=settings)
        if screenshot_path:
            raw_data["screenshot_path"] = screenshot_path

    try:
        item = ScrapedItem.model_validate(raw_data)
    except ValidationError as ve:
        logger.warning(MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL.format(url=url, exc=ve))
        return None, raw_data.get("page_type", ""), set(raw_data.keys()), raw_data

    logger.info(MSG_INFO_ADAPTIVE_EXTRACTION_SUCCESS_WITH_URL.format(url=url))
    log_structured_data(item.model_dump(mode="json"), settings=settings)
    non_empty_fields = {k for k, v in raw_data.items() if v not in [None, ""]}
    return item, raw_data.get("page_type", ""), non_empty_fields, raw_data


async def extract_adaptive_data(
    request: ScrapeRequest,
    *,
    settings: Settings,
) -> ScrapedItem | None:
    if request.context_hints is None:
        request.context_hints = extract_context_hints(request.text, request.url)
    prompt = build_prompt(
        text=request.text,
        url=request.url,
        prompt_style="enhanced",
        context_hints=request.context_hints,
    )
    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": prompt}]
    logger.debug(MSG_DEBUG_LLM_INITIAL_PROMPT.format(url=request.url, prompt=prompt))
    client = AsyncOpenAI(
        api_key=request.openai.api_key,
        project=request.openai.project_id,
    )

    best_score = 0
    best_fields: dict[str, Any] | None = None
    all_fields: dict[str, Any] = {}

    for attempt_num in range(1, settings.llm_schema_retries + 1):
        logger.debug(
            MSG_DEBUG_LLM_RETRY_ATTEMPT.format(
                attempt=attempt_num,
                total=settings.llm_schema_retries,
                url=request.url,
            )
        )

        content = await run_llm_with_retries(client, messages, settings, request.url)
        if content is None:
            return None

        item, page_type, observed_fields, raw_data = await process_llm_output(
            content=content,
            url=request.url,
            take_screenshot=request.take_screenshot,
            settings=settings,
        )

        all_fields.update({k: v for k, v in raw_data.items() if v is not None and v != ""})

        if item is not None:
            return item

        page_type = page_type or request.context_hints.get("page_type", "")
        required = get_required_fields(page_type) or IMPORTANT_FIELDS
        missing = required - observed_fields

        retry_message = (
            build_retry_prompt(best_fields or {}, missing)
            if missing
            else (
                "Please try to extract any additional useful fields from "
                "the content that may have been missed earlier. "
                "Ensure your output includes all relevant fields and metadata "
                "based on the page type and context. Return only valid JSON."
            )
        )

        messages[:] = messages[:1]
        messages.append({"role": "user", "content": retry_message})
        logger.debug(
            MSG_DEBUG_LLM_RETRY_PROMPT.format(
                url=request.url,
                attempt=attempt_num,
                message=retry_message,
            )
        )
        score = score_fields(observed_fields)
        logger.debug(
            MSG_DEBUG_FIELD_SCORE_PER_RETRY.format(
                url=request.url,
                attempt=attempt_num,
                score=score,
                fields=sorted(observed_fields),
            )
        )
        if score > best_score:
            best_score = score
            best_fields = copy.deepcopy(raw_data)

    # Try validating all_fields (merged across retries)
    if all_fields:
        try:
            item = ScrapedItem.model_validate(all_fields)
        except ValidationError as ve:
            logger.warning(MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL.format(url=request.url, exc=ve))
        else:
            logger.info(MSG_INFO_ADAPTIVE_EXTRACTION_SUCCESS_WITH_URL.format(url=request.url))
            return item

    # Fallback to best_fields if available
    if best_fields:
        logger.debug(MSG_DEBUG_USING_BEST_CANDIDATE_FIELDS.format(fields=list(best_fields.keys())))
        try:
            item = ScrapedItem.model_validate(best_fields)
        except ValidationError as ve:
            logger.warning(MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL.format(url=request.url, exc=ve))
        else:
            logger.info(MSG_INFO_ADAPTIVE_EXTRACTION_SUCCESS_WITH_URL.format(url=request.url))
            return item

    logger.warning(
        MSG_WARN_ADAPTIVE_EXTRACTION_FAILED_AFTER_RETRIES.format(
            attempts=settings.llm_schema_retries,
            url=request.url,
        )
    )
    return None
