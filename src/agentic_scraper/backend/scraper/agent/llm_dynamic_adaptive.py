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
import re
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
    select_best_candidate,
    try_validate_scraped_item,
)
from agentic_scraper.backend.scraper.agent.field_utils import (
    get_required_fields,
    normalize_keys,
)
from agentic_scraper.backend.scraper.agent.prompt_helpers import (
    build_prompt,
    build_retry_or_fallback_prompt,
)
from agentic_scraper.backend.scraper.models import ScrapedItem, ScrapeRequest

logger = logging.getLogger(__name__)

__all__ = ["extract_adaptive_data"]

RATE_LIMIT_RETRY_REGEX = re.compile(r"(?:retry|try again).*?(\d+(?:\.\d+)?)s", re.IGNORECASE)


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
                if not response.choices or not response.choices[0].message.content:
                    return None
                return response.choices[0].message.content.strip()
            except OpenAIError as e:
                handle_openai_exception(e, url, settings)
                raise

    return None


async def _attempt_llm_pass(
    content: str,
    url: str,
    settings: Settings,
    *,
    take_screenshot: bool,
) -> tuple[ScrapedItem | None, str, set[str], dict[str, Any]]:
    """
    Perform a single validation pass of the LLM response.

    Args:
        content (str): Raw string content from the LLM.
        url (str): The source page URL.
        settings (Settings): App-wide runtime settings.
        take_screenshot (bool): Whether to capture a screenshot if successful.

    Returns:
        tuple:
            - ScrapedItem | None: Validated result if successful.
            - str: Extracted page_type or "".
            - set[str]: Observed non-empty field names.
            - dict[str, Any]: Raw normalized output from the LLM.
    """
    raw_data = parse_llm_response(content, url, settings)
    if raw_data is None:
        return None, "", set(), {}

    raw_data = normalize_keys(raw_data)
    raw_data["url"] = url

    if take_screenshot:
        screenshot_path = await capture_optional_screenshot(url, settings)
        if screenshot_path:
            raw_data["screenshot_path"] = screenshot_path

    item = try_validate_scraped_item(raw_data, url, settings)
    non_empty_fields = {k for k, v in raw_data.items() if v not in [None, ""]}
    return item, raw_data.get("page_type", ""), non_empty_fields, raw_data


async def extract_adaptive_data(
    request: ScrapeRequest,
    *,
    settings: Settings,
) -> ScrapedItem | None:
    """
    Perform structured extraction with adaptive retry logic.

    Builds an enhanced prompt with context hints and allows multiple retry
    attempts to improve field coverage based on missing schema elements.

    Args:
        request (ScrapeRequest): Includes cleaned page text, URL, OpenAI creds, and context.
        settings (Settings): Controls retries, model parameters, and screenshot settings.

    Returns:
        ScrapedItem | None: Fully or partially validated item, or None on total failure.

    Raises:
        None: All retryable errors are handled internally.
    """
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

    api_key, project_id = retrieve_openai_credentials(request.openai)

    client = AsyncOpenAI(
        api_key=api_key,
        project=project_id,
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

        item, page_type, observed_fields, raw_data = await _attempt_llm_pass(
            content=content,
            url=request.url,
            settings=settings,
            take_screenshot=request.take_screenshot,
        )

        all_fields.update({k: v for k, v in raw_data.items() if v not in [None, ""]})

        if item is not None:
            return item

        page_type = (
            page_type or raw_data.get("page_type") or request.context_hints.get("page_type") or ""
        )
        required = get_required_fields(page_type) or IMPORTANT_FIELDS
        missing = required - observed_fields

        retry_prompt = build_retry_or_fallback_prompt(best_fields, missing)
        messages[:] = messages[:1]
        messages.append({"role": "user", "content": retry_prompt})

        logger.debug(
            MSG_DEBUG_LLM_RETRY_PROMPT.format(
                url=request.url,
                attempt=attempt_num,
                message=retry_prompt,
            )
        )

        score = score_and_log_fields(observed_fields, attempt_num, request.url)
        if score > best_score:
            best_score = score
            best_fields = copy.deepcopy(raw_data)

    if all_fields and best_fields != all_fields:
        item = try_validate_scraped_item(all_fields, request.url, settings)
        if item:
            return item
    if best_fields:
        item = try_validate_scraped_item(best_fields, request.url, settings)
        if item:
            return item
    logger.warning(
        MSG_WARN_ADAPTIVE_EXTRACTION_FAILED_AFTER_RETRIES.format(
            attempts=settings.llm_schema_retries,
            url=request.url,
        )
    )
    return select_best_candidate(best_fields or all_fields, request.url)
