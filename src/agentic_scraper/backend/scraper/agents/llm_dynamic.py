# src/agentic_scraper/backend/scraper/agents/llm_dynamic.py
"""
Dynamic LLM-based extraction agent (single-pass, flexible schema).

Responsibilities:
- Build a context-aware prompt (optionally enriched with page hints) and call
  OpenAI Chat Completions.
- Parse the JSON reply, normalize keys/values, compute a discovery score, and
  validate into `ScrapedItem`.
- Optionally attach a screenshot path to the result.

Public API:
- `extract_structured_data`: Orchestrates retry/backoff and calls the core impl.

Operational:
- Retries: Exponential backoff via `tenacity`; limited by `settings.retry_attempts`.
- Logging: Uses message constants; prompt is logged at DEBUG (sensitive content awareness).
- Cancellation: Handled at higher layers (pipeline/worker); this module doesn't poll.

Usage:
    from agentic_scraper.backend.scraper.agents.llm_dynamic import extract_structured_data
    item = await extract_structured_data(request, settings=settings)

Notes:
- We pass dict-shaped messages to the OpenAI client so the same structure also works
  with a local stub (used when the SDK isn't installed in CI/test envs).
- Key normalization aligns diverse LLM outputs with expected canonical fields.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agentic_scraper.backend.config.aliases import APIErrorT, OpenAIErrorT, RateLimitErrorT
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_LLM_PROMPT_WITH_URL,
    MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL,
    MSG_INFO_FIELD_DISCOVERY_SCORE,
    MSG_OPENAI_CLIENT_UNAVAILABLE,
)
from agentic_scraper.backend.scraper.agents.agent_helpers import (
    capture_optional_screenshot,
    handle_openai_exception,
    parse_llm_response,
    retrieve_openai_credentials,
    try_validate_scraped_item,
)
from agentic_scraper.backend.scraper.agents.field_utils import (
    detect_unavailable_fields,
    normalize_fields,
    normalize_keys,
    score_nonempty_fields,
)
from agentic_scraper.backend.scraper.agents.prompt_helpers import build_prompt

if TYPE_CHECKING:
    from agentic_scraper.backend.core.settings import Settings
    from agentic_scraper.backend.scraper.models import ScrapeRequest
    from agentic_scraper.backend.scraper.schemas import ScrapedItem

logger = logging.getLogger(__name__)

__all__ = ["extract_structured_data"]

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
              loudly if the real SDK isn't available, while keeping imports safe.
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
                    messages: list[dict[str, object]],
                    temperature: float,
                    max_tokens: int,
                ) -> object:
                    _ = (model, messages, temperature, max_tokens)
                    # Mirrors llm_fixed stub behavior: communicate SDK unavailability.
                    msg = MSG_OPENAI_CLIENT_UNAVAILABLE
                    raise RuntimeError(msg)

    _AsyncOpenAI_cls = _AsyncOpenAIStub

# Bind the public name exactly once so mypy doesn't see a redefinition.
AsyncOpenAI: type = _AsyncOpenAI_cls


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
async def extract_structured_data(
    request: ScrapeRequest,
    *,
    settings: Settings,
) -> ScrapedItem | None:
    """
    LLM-based structured data extraction using a dynamic prompt and retry logic.

    Args:
        request (ScrapeRequest): Prepared input (normalized URL/text, optional hints/creds).
        settings (Settings): Runtime configuration (model, tokens, temperature, retries).

    Returns:
        ScrapedItem | None: Validated item on success, else None (parse/validation failure
            or OpenAI error after retries).

    Notes:
        - This function wraps `_extract_impl` with tenacity retry/backoff.
        - Cancellation is handled by callers (pipeline/worker); we don't poll a cancel token here.
    """
    retry_on = (OpenAIErrorT, APIErrorT, RateLimitErrorT)

    # Tenacity governs when/what to retry; the attempt body remains small in _extract_impl.
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(settings.retry_attempts),
        wait=wait_exponential(
            multiplier=1,
            min=settings.retry_backoff_min,
            max=settings.retry_backoff_max,
        ),
        retry=retry_if_exception_type(retry_on),
        reraise=True,
    ):
        with attempt:
            return await _extract_impl(request=request, settings=settings)

    # Defensive: control flow should return from inside the retry loop or raise.
    return None


async def _extract_impl(
    *,
    request: ScrapeRequest,
    settings: Settings,
) -> ScrapedItem | None:
    """
    Single-attempt dynamic extraction against OpenAI Chat Completions.

    Build an enhanced prompt (with context hints when available), call the LLM,
    parse JSON, normalize fields/keys, compute a discovery score, optionally add
    a screenshot, and validate to `ScrapedItem`.

    Args:
        request (ScrapeRequest): Input including cleaned text, url, optional context hints.
        settings (Settings): Runtime config for model/temperature/token limits.

    Returns:
        ScrapedItem | None: Structured/validated item; None on empty content, parse failure,
            or validation failure.

    Notes:
        - We log the constructed prompt at DEBUG to aid reproducibility (be mindful of PII).
        - Messages are plain dicts so the same payload works with the stub client.
        - Screenshot capture is deferred until after a successful parse to avoid waste.
    """
    # Build the prompt with contextual hints; this improves field discovery.
    prompt = build_prompt(
        text=request.text,
        url=request.url,
        prompt_style="enhanced",
        context_hints=request.context_hints,
    )
    logger.debug(MSG_DEBUG_LLM_PROMPT_WITH_URL.format(url=request.url, prompt=prompt))

    # Dict-based messages keep compatibility with both real client and stub.
    messages_payload: list[dict[str, object]] = [{"role": "user", "content": prompt}]

    # Validate and extract OpenAI credentials early; fail fast if invalid.
    api_key, project_id = retrieve_openai_credentials(request.openai)
    client = AsyncOpenAI(api_key=api_key, project=project_id)

    try:
        # Both the real SDK and the stub expose: client.chat.completions.create(...)
        response: Any = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages_payload,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        # OpenAI SDK shape: choices[0].message.content (string or None)
        content = response.choices[0].message.content
        if not content:
            logger.warning(MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL.format(url=request.url))
            return None

        # Parse JSON (with repair pass) and bail quietly on failure.
        raw_data = parse_llm_response(content, request.url, settings)
        if raw_data is None:
            return None

        # Normalize keys (e.g., "cost" -> "price") and ensure url is present.
        raw_data = normalize_keys(raw_data)
        raw_data["url"] = request.url

        # Score discovery quality and note explicitly unavailable fields (e.g., "N/A").
        unavailable_fields = detect_unavailable_fields(raw_data)
        score = score_nonempty_fields(raw_data)
        logger.info(
            MSG_INFO_FIELD_DISCOVERY_SCORE.format(
                url=request.url,
                score=score,
                num_unavailable=len(unavailable_fields),
            )
        )

        # Normalize values (types/placeholders) for downstream validation.
        normalized = normalize_fields(raw_data)

        # Optional screenshot (post-parse to avoid unnecessary browser work on failures).
        if request.take_screenshot:
            screenshot_path = await capture_optional_screenshot(request.url, settings)
            if screenshot_path:
                # Only set if absent to avoid overwriting any upstream value.
                normalized.setdefault("screenshot_path", screenshot_path)

        # Final schema validation + structured logging handled inside the helper.
        return try_validate_scraped_item(normalized, request.url, settings)

    except (RateLimitErrorT, APIErrorT, OpenAIErrorT) as e:
        # Uniform, verbosity-aware handling of OpenAI exceptions.
        handle_openai_exception(e, url=request.url, settings=settings)
        return None
