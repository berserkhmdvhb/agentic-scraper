# src/agentic_scraper/backend/scraper/agents/llm_dynamic_adaptive.py
"""
Adaptive LLM-based extraction agent with schema-aware retries.

Responsibilities:
- Run a multi-pass LLM extraction loop that uses prior results to focus retries.
- Normalize/validate LLM output and track the “best so far” fields/items.
- Decide early exit vs. additional discovery passes based on progress heuristics.

Public API:
- `extract_adaptive_data`: Orchestrates the full adaptive flow and returns a `ScrapedItem`.

Operational:
- Retries: Per-attempt OpenAI calls use tenacity (random exponential backoff) and
  the outer loop is governed by `settings.llm_schema_retries`.
- Logging: Uses message constants; prompts and retry details logged at DEBUG.
- Cancellation: Managed by the pipeline/worker layer; this module does not poll.

Usage:
    from agentic_scraper.backend.scraper.agents.llm_dynamic_adaptive import extract_adaptive_data
    item = await extract_adaptive_data(request, settings=settings)

Notes:
- We pass dict-shaped messages compatible with both the real OpenAI client and a local stub.
- The algorithm maintains multiple “best” notions (best fields overall vs best validated item)
  to maximize the chance of returning a valid result at the end.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Protocol

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from agentic_scraper.backend.config.aliases import APIErrorT, OpenAIErrorT, RateLimitErrorT
from agentic_scraper.backend.config.constants import IMPORTANT_FIELDS
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_FINAL_DISCOVERY_RETRY_TRIGGERED,
    MSG_DEBUG_LLM_INITIAL_PROMPT,
    MSG_DEBUG_LLM_RETRY_ATTEMPT,
    MSG_DEBUG_LLM_RETRY_PROMPT,
    MSG_OPENAI_CLIENT_UNAVAILABLE,
    MSG_WARN_ADAPTIVE_EXTRACTION_FAILED_AFTER_RETRIES,
)
from agentic_scraper.backend.scraper.agents.agent_helpers import (
    capture_optional_screenshot,
    extract_context_hints,
    handle_openai_exception,
    parse_llm_response,
    retrieve_openai_credentials,
    score_and_log_fields,
    should_exit_early,
    try_validate_scraped_item,
)
from agentic_scraper.backend.scraper.agents.field_utils import (
    detect_unavailable_fields,
    get_required_fields,
    normalize_fields,
    normalize_keys,
)
from agentic_scraper.backend.scraper.agents.prompt_helpers import (
    _sort_fields_by_weight,
    build_prompt,
    build_retry_or_fallback_prompt,
)
from agentic_scraper.backend.scraper.models import RetryContext  # used at runtime

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

    from agentic_scraper.backend.core.settings import Settings
    from agentic_scraper.backend.scraper.models import ScrapeRequest
    from agentic_scraper.backend.scraper.schemas import ScrapedItem

logger = logging.getLogger(__name__)

__all__ = ["extract_adaptive_data"]

# -----------------------------------------------------------------------------
# OpenAI client import with safe fallback (single assignment for mypy)
# -----------------------------------------------------------------------------
try:  # pragma: no cover (import-path dependent)
    from openai import AsyncOpenAI as _ImportedAsyncOpenAI

    _AsyncOpenAI_cls: type = _ImportedAsyncOpenAI
except ImportError:  # pragma: no cover

    class _AsyncOpenAIStub:
        """Minimal stub that mimics `openai.AsyncOpenAI` enough for our usage and tests.

        Notes:
            - The stub raises a clear RuntimeError in `.create(...)` so calls fail
              loudly if the real SDK isn't present, while keeping imports safe.
        """

        def __init__(self, *, api_key: str | None = None, project: str | None = None) -> None:
            self.api_key = api_key
            self.project = project
            self.chat = self.Chat()

        class Chat:
            def __init__(self) -> None:
                self.completions = self.Completions()

            class Completions:
                @staticmethod
                async def create(
                    *,
                    model: str,
                    messages: list[dict[str, object]] | list[object],
                    temperature: float,
                    max_tokens: int,
                ) -> object:
                    _ = (model, messages, temperature, max_tokens)
                    msg = MSG_OPENAI_CLIENT_UNAVAILABLE
                    raise RuntimeError(msg)

    _AsyncOpenAI_cls = _AsyncOpenAIStub

# Bind the public name exactly once so mypy doesn't see a redefinition.
AsyncOpenAI: type = _AsyncOpenAI_cls


# -----------------------------------------------------------------------------
# Protocols describing the parts of the OpenAI response we actually use
# -----------------------------------------------------------------------------
class _MessageProto(Protocol):
    """Subset of the OpenAI message object used in this module (structural typing)."""

    @property
    def content(self) -> str | None: ...


class _ChoiceProto(Protocol):
    """Subset of the OpenAI choice object used in this module (structural typing)."""

    @property
    def message(self) -> _MessageProto: ...


class _ResponseProto(Protocol):
    """Subset of the OpenAI response object used in this module (structural typing)."""

    @property
    def choices(self) -> Sequence[_ChoiceProto]: ...


class _CompletionsProto(Protocol):
    """Subset of the OpenAI chat.completions client used in this module."""

    async def create(
        self,
        *,
        model: str,
        messages: list[ChatCompletionMessageParam],
        temperature: float,
        max_tokens: int,
    ) -> _ResponseProto: ...


class _ChatProto(Protocol):
    """Subset of the OpenAI client.chat accessor."""

    @property
    def completions(self) -> _CompletionsProto: ...


class _ClientProto(Protocol):
    """Subset of the OpenAI Async client needed at call sites."""

    @property
    def chat(self) -> _ChatProto: ...


# -----------------------------------------------------------------------------
# LLM call runner with retries
# -----------------------------------------------------------------------------
async def run_llm_with_retries(
    client: _ClientProto,
    messages: list[ChatCompletionMessageParam],
    settings: Settings,
    url: str,
) -> str | None:
    """
    Run the LLM call with retries for robustness against transient OpenAI errors.

    Args:
        client (_ClientProto): OpenAI client (real or stub) with chat.completions.
        messages (list[ChatCompletionMessageParam]): Conversation payload to send.
        settings (Settings): Runtime config (model, tokens, temperature, retry policy).
        url (str): URL for logging context.

    Returns:
        str | None: Content string (LLM JSON) on success, else None.

    Notes:
        - Tenacity governs retry behavior; OpenAI-style exceptions are handled
          and logged via `handle_openai_exception` before returning None.
    """
    # Retry only on OpenAI-family errors; JSON parse/validation issues are not retried here.
    retry_on = (OpenAIErrorT, APIErrorT, RateLimitErrorT)

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(settings.retry_attempts),
        wait=wait_random_exponential(
            multiplier=1,
            min=settings.retry_backoff_min,
            max=settings.retry_backoff_max,
        ),
        retry=retry_if_exception_type(retry_on),
        reraise=True,
    ):
        with attempt:
            try:
                response: _ResponseProto = await client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                )
                # Response shape is unified via structural protocols above
                content_obj = response.choices[0].message.content
                if not isinstance(content_obj, str) or not content_obj:
                    return None
                return content_obj.strip()
            except retry_on as e:
                # Design choice: treat OpenAI-family errors as handled and stop the attempt chain.
                # Tests expect us to return None rather than propagate.
                handle_openai_exception(e, url=url, settings=settings)
                return None
    return None


# -----------------------------------------------------------------------------
# Single LLM pass parsing/validation
# -----------------------------------------------------------------------------
async def _attempt_llm_pass(
    content: str,
    url: str,
    settings: Settings,
) -> tuple[ScrapedItem | None, str, set[str], dict[str, Any], set[str]]:
    """
    Perform a single validation pass of the LLM response.

    Args:
        content (str): Raw JSON (string) returned from the LLM.
        url (str): Source URL for logging context.
        settings (Settings): Runtime config for parsing/validation behavior.

    Returns:
        tuple[ScrapedItem | None, str, set[str], dict[str, Any], set[str]]:
            (validated_item_or_none,
             page_type,                # heuristic from JSON
             non_empty_fields,         # keys with non-empty values (excl. placeholders)
             normalized_fields,        # value-normalized dict (types/placeholders handled)
             unavailable_fields)       # syntactic placeholders (e.g., "N/A")
    """
    raw_data = parse_llm_response(content, url, settings)
    if raw_data is None:
        # Parsing failed after repair attempts; stop this pass.
        return None, "", set(), {}, set()

    raw_data["url"] = url
    raw_data = normalize_keys(raw_data)  # Align aliases to canonical names early.

    # Detect placeholders (e.g., "N/A") before value normalization.
    unavailable_fields = detect_unavailable_fields(raw_data)

    # Identify fields that are actually non-empty (and not placeholders).
    non_empty_fields = {
        k for k, v in raw_data.items() if v not in [None, ""] and k not in unavailable_fields
    }

    # Normalize values to expected types/format for schema validation.
    normalized = normalize_fields(raw_data)

    # Validate against ScrapedItem; returns None if validation fails.
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
    client: _ClientProto,
) -> tuple[bool, RetryContext]:
    """
    Perform a single adaptive retry pass with updated prompt and result evaluation.

    Args:
        attempt_num (int): 1-based retry attempt counter.
        ctx (RetryContext): Mutable state tracking best scores/items/fields.
        initial_messages (list[ChatCompletionMessageParam]): Seed system+user messages.
        request (ScrapeRequest): Current scrape request (url/text/hints).
        settings (Settings): Runtime config including retry limits.
        client (_ClientProto): OpenAI client.

    Returns:
        tuple[bool, RetryContext]:
            (done, ctx) where `done=True` signals the outer loop to stop.

    Notes:
        - We keep conversation state minimal (last assistant + a fresh user retry prompt)
          to avoid drifting the context window while still steering the model.
    """
    logger.debug(
        MSG_DEBUG_LLM_RETRY_ATTEMPT.format(
            attempt=attempt_num,
            total=settings.llm_schema_retries,
            url=request.url,
        )
    )

    # Run the current message stack (ctx.messages) and add the assistant reply to context.
    content = await run_llm_with_retries(client, ctx.messages, settings, request.url)
    if content is None:
        # Treat as handled (e.g., rate limit); signal the loop to stop.
        return True, ctx

    assistant_msg: ChatCompletionMessageParam = {"role": "assistant", "content": content}
    ctx.messages.append(assistant_msg)

    # Parse/validate/normalize the single pass result.
    item, page_type, observed_fields, raw_data, unavailable_fields = await _attempt_llm_pass(
        content=content,
        url=request.url,
        settings=settings,
    )

    # Track all non-empty fields seen across attempts (union).
    ctx.all_fields.update({k: v for k, v in raw_data.items() if v not in [None, ""]})

    # Score fields and update "best" trackers.
    score = score_and_log_fields(observed_fields, attempt_num, request.url, raw_data)
    if score > ctx.best_score:
        ctx.best_score = score
        ctx.best_fields = copy.deepcopy(raw_data)
    if item is not None and score > ctx.best_valid_score:
        ctx.best_valid_item = item
        ctx.best_valid_score = score

    # Determine required fields based on inferred/known page type.
    page_type = (
        page_type
        or raw_data.get("page_type")
        or (request.context_hints.get("page_type") if request.context_hints else None)
        or ""
    )
    required = get_required_fields(page_type) or IMPORTANT_FIELDS

    best_keys = set(ctx.best_fields or {})
    # Exclude fields explicitly marked unavailable to avoid futile retries.
    missing = set(_sort_fields_by_weight(required - best_keys - unavailable_fields))

    # Final discovery push:
    # If we have a valid item AND nothing is missing yet AND we haven't done an extra
    # discovery pass, do one more attempt focused on uncovering additional fields.
    if item is not None and not missing and not ctx.has_done_discovery:
        ctx.has_done_discovery = True
        logger.debug(MSG_DEBUG_FINAL_DISCOVERY_RETRY_TRIGGERED.format(url=request.url))
        return False, ctx

    # Early-exit heuristic: if we made no meaningful progress vs. the current best, stop.
    if should_exit_early(
        item=item,
        raw_data=raw_data,
        best_fields=ctx.best_fields,
        missing=missing,
        url=request.url,
    ):
        return True, ctx

    # Build a focused retry prompt and reset the convo window:
    # [system], [last assistant], [new user prompt]
    retry_prompt = build_retry_or_fallback_prompt(ctx.best_fields, missing)
    retry_user_msg: ChatCompletionMessageParam = {"role": "user", "content": retry_prompt}
    ctx.messages = [
        initial_messages[0],  # system
        ctx.messages[-1],  # last assistant output
        retry_user_msg,  # new user instruction
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
    """
    Attempt final validation and return the best available result after retries.

    Args:
        best_valid_item (ScrapedItem | None): Highest-scoring validated item (if any).
        best_fields (dict[str, Any] | None): Best raw fields observed (not necessarily validated).
        all_fields (dict[str, Any]): Union of all non-empty fields observed.
        request (ScrapeRequest): Original request (used for URL and screenshot flag).
        settings (Settings): Runtime config incl. screenshot directory.

    Returns:
        ScrapedItem | None: Best validated item, or a validated candidate from
            `best_fields`/`all_fields`, else None if all attempts fail.

    Notes:
        - We attempt screenshot capture once here if we have any candidate to annotate.
        - We do not mutate `best_fields` unless necessary (only to attach a screenshot path).
    """
    screenshot_path: str | None = None
    if request.take_screenshot and (best_valid_item or best_fields):
        screenshot_path = await capture_optional_screenshot(request.url, settings)
        if best_valid_item and screenshot_path:
            # Safe to enrich the validated item with a screenshot path.
            best_valid_item.screenshot_path = screenshot_path

    if best_valid_item:
        return best_valid_item

    # Try the best raw fields first, then union of all fields as a last resort.
    for candidate in (best_fields, all_fields):
        if candidate:
            enriched = dict(candidate)
            if screenshot_path:
                enriched["screenshot_path"] = screenshot_path
            item = try_validate_scraped_item(enriched, request.url, settings)
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
    Perform structured data extraction using adaptive retry logic.

    Args:
        request (ScrapeRequest): Cleaned text/url, optional context hints and OpenAI creds.
        settings (Settings): Runtime config guiding retries, token limits, etc.

    Returns:
        ScrapedItem | None: Validated item on success; None if parsing/validation fails
            across all attempts.

    Examples:
        item = await extract_adaptive_data(req, settings=settings)

    Notes:
        - If `request.context_hints` is missing, we derive them from HTML+URL before the first call.
        - Conversation starts with a neutral system message and an enhanced user prompt.
    """
    if request.context_hints is None:
        # Generate contextual hints once to improve initial prompt grounding.
        request.context_hints = extract_context_hints(request.text, request.url)

    prompt = build_prompt(
        text=request.text,
        url=request.url,
        prompt_style="enhanced",
        context_hints=request.context_hints,
    )

    # Keep the initial system message concise to reduce token overhead.
    sys_msg: ChatCompletionMessageParam = {
        "role": "system",
        "content": "You are a helpful assistant that extracts structured data in JSON format.",
    }
    user_msg: ChatCompletionMessageParam = {"role": "user", "content": prompt}

    initial_messages: list[ChatCompletionMessageParam] = [sys_msg, user_msg]
    logger.debug(MSG_DEBUG_LLM_INITIAL_PROMPT.format(url=request.url, prompt=prompt))

    # Validate/prepare credentials up front; fail fast if missing/invalid.
    api_key, project_id = retrieve_openai_credentials(request.openai)
    client: _ClientProto = AsyncOpenAI(api_key=api_key, project=project_id)  # structural typing

    # RetryContext tracks scores, best fields, best validated item, and the running message list.
    ctx = RetryContext(
        messages=list(initial_messages),
        best_score=0.0,
        best_valid_score=0.0,
        best_fields=None,
        best_valid_item=None,
        all_fields={},
    )

    # Adaptive loop: keep attempts bounded by settings.llm_schema_retries.
    for attempt_num in range(1, settings.llm_schema_retries + 1):
        done, ctx = await process_retry(
            attempt_num,
            ctx,
            initial_messages=list(initial_messages),
            request=request,
            settings=settings,
            client=client,
        )
        if done:
            # Exit when the retry step signals early-stop (no further useful progress).
            if ctx.best_valid_item:
                return ctx.best_valid_item
            break

    # Fallback consolidation: prefer best validated item, else validate best/all fields.
    return await handle_fallback(
        ctx.best_valid_item,
        ctx.best_fields,
        ctx.all_fields,
        request,
        settings,
    )
