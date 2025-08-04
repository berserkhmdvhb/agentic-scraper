"""
Adaptive LLM-based extraction agent with schema-aware retries.

This agent performs structured data extraction from web page content using OpenAI's Chat API.
Unlike the simpler dynamic agent, it performs multiple passes with adaptive retry prompts
that attempt to recover missing fields based on observed output.

Features:
- Contextual prompt building with metadata hints
- Self-healing retry logic for incomplete JSON
- Scoring and fallback selection of best partial attempt
- Optional screenshot capture and structured logging

Primary entrypoint:
    - extract_adaptive_data(request, settings)
"""

import copy
import logging
from typing import Any

from openai import AsyncOpenAI, OpenAIError
from openai.types.chat import ChatCompletionMessageParam
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from agentic_scraper.backend.config.constants import IMPORTANT_FIELDS
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_FINAL_DISCOVERY_RETRY_TRIGGERED,
    MSG_DEBUG_LLM_INITIAL_PROMPT,
    MSG_DEBUG_LLM_RETRY_ATTEMPT,
    MSG_DEBUG_LLM_RETRY_PROMPT,
    MSG_WARN_ADAPTIVE_EXTRACTION_FAILED_AFTER_RETRIES,
)
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.agent.agent_helpers import (
    capture_optional_screenshot,
    extract_context_hints,
    handle_openai_exception,
    parse_llm_response,
    retrieve_openai_credentials,
    score_and_log_fields,
    should_exit_early,
    try_validate_scraped_item,
)
from agentic_scraper.backend.scraper.agent.field_utils import (
    detect_unavailable_fields,
    get_required_fields,
    normalize_fields,
    normalize_keys,
)
from agentic_scraper.backend.scraper.agent.prompt_helpers import (
    _sort_fields_by_weight,
    build_prompt,
    build_retry_or_fallback_prompt,
)
from agentic_scraper.backend.scraper.models import RetryContext, ScrapedItem, ScrapeRequest

logger = logging.getLogger(__name__)

__all__ = ["extract_adaptive_data"]


async def run_llm_with_retries(
    client: AsyncOpenAI,
    messages: list[ChatCompletionMessageParam],
    settings: Settings,
    url: str,
) -> str | None:
    """
    Run the LLM call with retries for robustness against transient OpenAI errors.

    Args:
        client (AsyncOpenAI): Authenticated OpenAI client.
        messages (list): List of chat messages to send to the LLM.
        settings (Settings): Retry and model configuration.
        url (str): Source URL for logging context.

    Returns:
        str | None: LLM response content or None on repeated failure.

    Raises:
        OpenAIError: If all retry attempts fail.
    """
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
                content = response.choices[0].message.content
                if not content or not isinstance(content, str):
                    return None
                return content.strip()
            except OpenAIError as e:
                handle_openai_exception(e, url, settings)
                raise

    return None


async def _attempt_llm_pass(
    content: str,
    url: str,
    settings: Settings,
) -> tuple[ScrapedItem | None, str, set[str], dict[str, Any], set[str]]:
    """
    Perform a single validation pass of the LLM response.

    Args:
        content (str): Raw string content from the LLM.
        url (str): The source page URL.
        settings (Settings): App-wide runtime settings.

    Returns:
        tuple:
            - ScrapedItem | None: Validated result if successful.
            - str: Extracted page_type or "".
            - set[str]: Observed non-empty field names (excluding null/blank).
            - dict[str, Any]: Raw normalized output from the LLM.
            - set[str]: Fields detected as explicitly marked unavailable (e.g., "N/A").
    """
    raw_data = parse_llm_response(content, url, settings)
    if raw_data is None:
        return None, "", set(), {}, set()

    raw_data["url"] = url
    raw_data = normalize_keys(raw_data)

    # Detect unavailable fields *before* normalization
    unavailable_fields = detect_unavailable_fields(raw_data)

    # Identify non-empty fields (excluding null/empty/placeholder)
    non_empty_fields = {
        k for k, v in raw_data.items() if v not in [None, ""] and k not in unavailable_fields
    }

    # Normalize only for validation
    normalized = normalize_fields(raw_data)
    item = try_validate_scraped_item(normalized, url, settings)

    return item, raw_data.get("page_type", ""), non_empty_fields, normalized, unavailable_fields


# ruff: noqa: PLR0913
async def process_retry(
    attempt_num: int,
    ctx: RetryContext,
    *,
    initial_messages: list[ChatCompletionMessageParam],
    request: ScrapeRequest,
    settings: Settings,
    client: AsyncOpenAI,
) -> tuple[bool, RetryContext]:
    logger.debug(
        MSG_DEBUG_LLM_RETRY_ATTEMPT.format(
            attempt=attempt_num,
            total=settings.llm_schema_retries,
            url=request.url,
        )
    )

    content = await run_llm_with_retries(client, ctx.messages, settings, request.url)
    if content is None:
        return True, ctx

    ctx.messages.append({"role": "assistant", "content": content})

    item, page_type, observed_fields, raw_data, unavailable_fields = await _attempt_llm_pass(
        content=content,
        url=request.url,
        settings=settings,
    )

    ctx.all_fields.update({k: v for k, v in raw_data.items() if v not in [None, ""]})

    score = score_and_log_fields(observed_fields, attempt_num, request.url, raw_data)
    if score > ctx.best_score:
        ctx.best_score = score
        ctx.best_fields = copy.deepcopy(raw_data)
    if item is not None and score > ctx.best_valid_score:
        ctx.best_valid_item = item
        ctx.best_valid_score = score

    page_type = (
        page_type
        or raw_data.get("page_type")
        or (request.context_hints.get("page_type") if request.context_hints else None)
        or ""
    )
    required = get_required_fields(page_type) or IMPORTANT_FIELDS
    best_keys = set(ctx.best_fields or {})
    missing = set(_sort_fields_by_weight(required - best_keys - unavailable_fields))

    # ─── Final Discovery Retry ────────────────────────────────────────────────
    if item is not None and not missing and not ctx.has_done_discovery:
        ctx.has_done_discovery = True
        logger.debug(MSG_DEBUG_FINAL_DISCOVERY_RETRY_TRIGGERED.format(url=request.url))
        # Force one last retry to discover optional fields
        return False, ctx

    if should_exit_early(
        item=item,
        raw_data=raw_data,
        best_fields=ctx.best_fields,
        missing=missing,
        url=request.url,
    ):
        return True, ctx

    retry_prompt = build_retry_or_fallback_prompt(ctx.best_fields, missing)
    ctx.messages = [
        initial_messages[0],
        ctx.messages[-1],  # last assistant output
        {"role": "user", "content": retry_prompt},
    ]
    logger.debug(
        MSG_DEBUG_LLM_RETRY_PROMPT.format(
            url=request.url,
            attempt=attempt_num,
            message=retry_prompt,
        )
    )

    return False, ctx


async def handle_fallback(
    best_valid_item: ScrapedItem | None,
    best_fields: dict[str, Any] | None,
    all_fields: dict[str, Any],
    request: ScrapeRequest,
    settings: Settings,
) -> ScrapedItem | None:
    screenshot_path: str | None = None
    if request.take_screenshot and (best_valid_item or best_fields):
        screenshot_path = await capture_optional_screenshot(request.url, settings)
        if best_valid_item and screenshot_path:
            best_valid_item.screenshot_path = screenshot_path

    if best_valid_item:
        return best_valid_item

    for candidate in (best_fields, all_fields):
        if candidate:
            if screenshot_path:
                candidate["screenshot_path"] = screenshot_path
            item = try_validate_scraped_item(candidate, request.url, settings)
            if item:
                return item

    logger.warning(
        MSG_WARN_ADAPTIVE_EXTRACTION_FAILED_AFTER_RETRIES.format(
            attempts=settings.llm_schema_retries,
            url=request.url,
        )
    )
    return None


async def extract_adaptive_data(
    request: ScrapeRequest,
    *,
    settings: Settings,
) -> ScrapedItem | None:
    """
    Perform structured extraction with adaptive retry logic.
    """
    if request.context_hints is None:
        request.context_hints = extract_context_hints(request.text, request.url)

    prompt = build_prompt(
        text=request.text,
        url=request.url,
        prompt_style="enhanced",
        context_hints=request.context_hints,
    )

    initial_messages: list[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": "You are a helpful assistant that extracts structured data in JSON format.",
        },
        {"role": "user", "content": prompt},
    ]

    logger.debug(MSG_DEBUG_LLM_INITIAL_PROMPT.format(url=request.url, prompt=prompt))

    api_key, project_id = retrieve_openai_credentials(request.openai)
    client = AsyncOpenAI(api_key=api_key, project=project_id)

    ctx = RetryContext(
        messages=initial_messages.copy(),
        best_score=0.0,
        best_valid_score=0.0,
        best_fields=None,
        best_valid_item=None,
        all_fields={},
    )

    for attempt_num in range(1, settings.llm_schema_retries + 1):
        done, ctx = await process_retry(
            attempt_num,
            ctx,
            initial_messages=initial_messages,
            request=request,
            settings=settings,
            client=client,
        )
        if done and ctx.best_valid_item:
            return ctx.best_valid_item

    return await handle_fallback(
        ctx.best_valid_item,
        ctx.best_fields,
        ctx.all_fields,
        request,
        settings,
    )
