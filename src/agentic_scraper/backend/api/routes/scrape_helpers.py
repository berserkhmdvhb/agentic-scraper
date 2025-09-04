"""
Helper utilities for scrape route orchestration (non-endpoint module).

Responsibilities:
- Resolve runtime configuration and OpenAI credentials for a scrape run.
- Transition job state safely (RUNNING/SUCCEEDED/FAILED) with terminal guards.
- Run the scraper pipeline and convert results into API DTOs.
- Emit lightweight debug logs for dynamic fields to aid observability.

Public API:
- (Internal helpers; not a public route surface. Functions are intentionally prefixed with `_`.)

Operational:
- Concurrency: Designed to be called from async route handlers / tasks.
- Logging: Uses structured message constants; avoids leaking secrets.

Usage:
    from agentic_scraper.backend.api.routes.scrape_helpers import _mark_running
    _mark_running(job_id)
    # Typically used indirectly by the /scrapes routes.

Notes:
- Job state transitions are defensive: terminal states are respected and never overwritten.
- Inline OpenAI credentials that look masked (e.g., "****") are ignored in favor of stored creds.
"""

import asyncio
import logging
from datetime import datetime, timezone

from agentic_scraper.backend.api.models import AuthUser
from agentic_scraper.backend.api.schemas.scrape import (
    ScrapeCreate,
    ScrapeResultDynamic,
    ScrapeResultFixed,
)
from agentic_scraper.backend.api.stores.job_store import get_job, update_job
from agentic_scraper.backend.api.stores.user_store import load_user_credentials
from agentic_scraper.backend.config.constants import SCRAPER_CONFIG_FIELDS
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_SCRAPE_CONFIG_MERGED,
    MSG_HTTP_MISSING_OPENAI_CREDS,
    MSG_INFO_INLINE_KEY_MASKED_FALLBACK,
    MSG_JOB_FAILED,
    MSG_JOB_SKIP_MARK_FAILED_TERMINAL,
    MSG_JOB_SKIP_MARK_RUNNING_TERMINAL,
    MSG_JOB_STARTED,
    MSG_JOB_SUCCEEDED,
    MSG_LOG_DEBUG_DYNAMIC_EXTRAS,
    MSG_LOG_DYNAMIC_EXTRAS_ERROR,
)
from agentic_scraper.backend.config.types import AgentMode, JobStatus, OpenAIConfig
from agentic_scraper.backend.core.settings import Settings, get_settings
from agentic_scraper.backend.scraper.pipeline import PipelineOptions, scrape_with_stats

logger = logging.getLogger(__name__)
settings = get_settings()


def _masked(s: str | None) -> bool:
    """
    Heuristically detect if a secret-like string is masked.

    Args:
        s (str | None): The candidate string (e.g., API key) to inspect.

    Returns:
        bool: True if the string appears masked (contains common mask glyphs), else False.

    Notes:
        - This is a best-effort check looking for characters like '*', '•', '●', '·'.
        - Used to decide whether to ignore inline OpenAI credentials.
    """
    if not s:
        return False
    return any(ch in s for ch in ("*", "•", "●", "·"))


def _mark_running(job_id: str) -> None:
    """
    Transition a job to RUNNING if it is not already terminal.

    Args:
        job_id (str): The identifier of the job to update.

    Returns:
        None

    Notes:
        - No-op if the job is already CANCELED/SUCCEEDED/FAILED.
        - Updates `updated_at` to the current UTC time.
    """
    # Read a snapshot to decide if we can transition to RUNNING.
    current = get_job(job_id)
    if not current:
        return
    status_lower = str(current.get("status", "")).lower()
    if status_lower in {"canceled", "succeeded", "failed"}:
        logger.debug(MSG_JOB_SKIP_MARK_RUNNING_TERMINAL.format(job_id=job_id, status=status_lower))
        return

    update_job(job_id, status=JobStatus.RUNNING, updated_at=datetime.now(timezone.utc))
    logger.info(MSG_JOB_STARTED.format(job_id=job_id))


def _resolve_openai_creds_or_fail(
    job_id: str,
    payload: ScrapeCreate,
    user: AuthUser,
) -> OpenAIConfig | None:
    """
    Resolve OpenAI credentials for this run and enforce prerequisites.

    Strategy:
        - If inline credentials look masked (e.g., "***"), ignore them and fall back
          to stored credentials.
        - If the selected agent mode requires LLM and no credentials are available,
          mark the job as FAILED and return None.

    Args:
        job_id (str): The target job id (used for status/error updates).
        payload (ScrapeCreate): The incoming scrape request payload.
        user (AuthUser): The authenticated user context.

    Returns:
        OpenAIConfig | None: Resolved credentials if available; otherwise None
            (after marking job FAILED when LLM is required).

    Raises:
        None: Errors are handled internally with job updates/logging.
    """
    inline = payload.openai_credentials
    # Ignore obviously masked inline keys to avoid treating UI previews as real secrets.
    if inline and _masked(getattr(inline, "api_key", None)):
        logger.info(MSG_INFO_INLINE_KEY_MASKED_FALLBACK)
        inline = None

    needs_llm = payload.agent_mode != AgentMode.RULE_BASED
    creds: OpenAIConfig | None = inline or load_user_credentials(user["sub"])

    if needs_llm and not creds:
        update_job(
            job_id,
            status=JobStatus.FAILED,
            error=MSG_HTTP_MISSING_OPENAI_CREDS,
            progress=0.0,
            updated_at=datetime.now(timezone.utc),
        )
        logger.error(MSG_JOB_FAILED.format(job_id=job_id, error=MSG_HTTP_MISSING_OPENAI_CREDS))
        return None

    return creds


def _merge_runtime_settings(payload: ScrapeCreate) -> Settings:
    """
    Merge request-provided scraper configuration into a copy of global settings.

    Only fields enumerated in `SCRAPER_CONFIG_FIELDS` are merged.

    Args:
        payload (ScrapeCreate): The incoming scrape request.

    Returns:
        Settings: A cloned `Settings` object with request overrides applied.

    Notes:
        - Emits a debug log of the merged config values for traceability.
    """
    # Extract only whitelisted fields from the payload to avoid accidental overrides.
    config_values = payload.model_dump(include=set(SCRAPER_CONFIG_FIELDS))
    merged: Settings = settings.model_copy(update=config_values)
    logger.debug(MSG_DEBUG_SCRAPE_CONFIG_MERGED.format(config=config_values))
    return merged


async def _run_pipeline_and_build_result(
    payload: ScrapeCreate,
    merged_settings: Settings,
    creds: OpenAIConfig | None,
    cancel_event: asyncio.Event | None,
    job_id: str,
) -> tuple[ScrapeResultDynamic | ScrapeResultFixed, bool]:
    """
    Execute the scrape pipeline and adapt the result to the correct API DTO.

    Decides between fixed vs. dynamic result envelopes based on `agent_mode`, then
    logs a minimal debug summary of dynamic extras (first item's keys).

    Args:
        payload (ScrapeCreate): Validated request payload.
        merged_settings (Settings): Runtime settings (global + overrides).
        creds (OpenAIConfig | None): Resolved OpenAI credentials (may be None for rule-based).
        cancel_event (asyncio.Event | None): Optional cooperative cancel signal.
        job_id (str): Job identifier for cancellation checks.

    Returns:
        tuple[ScrapeResultDynamic | ScrapeResultFixed, bool]:
            - The result envelope DTO.
            - A boolean flag indicating whether the run reported `was_canceled`.

    Raises:
        Exception: Any exceptions are expected to be handled by the caller, which
                   will transition the job to FAILED as appropriate.
    """
    urls = [str(u) for u in payload.urls]

    # Expose a store-backed should_cancel() to handle cross-process events/races.
    def _should_cancel() -> bool:
        j = get_job(job_id)
        # Fallback: rely on cancel_event if job lookup isn't available
        if j is None:
            return bool(cancel_event and cancel_event.is_set())
        return str(j.get("status", "")).lower() == "canceled"

    items, stats = await scrape_with_stats(
        urls,
        settings=merged_settings,
        openai=creds,
        options=PipelineOptions(
            cancel_event=cancel_event,
            should_cancel=_should_cancel,
            job_hooks=None,
        ),
    )

    # Construct the correct result envelope based on agent mode.
    result_model: ScrapeResultDynamic | ScrapeResultFixed
    if payload.agent_mode in {AgentMode.LLM_FIXED, AgentMode.RULE_BASED}:
        result_model = ScrapeResultFixed.from_internal(items, stats)
    else:
        result_model = ScrapeResultDynamic.from_internal(items, stats)

    _debug_log_dynamic_extras(result_model, payload)

    was_canceled = bool(stats.get("was_canceled"))
    return result_model, was_canceled


def _debug_log_dynamic_extras(
    result_model: ScrapeResultDynamic | ScrapeResultFixed,
    payload: ScrapeCreate,
) -> None:
    """
    Emit a best-effort debug log of dynamic keys from the first result item.

    Args:
        result_model (ScrapeResultDynamic | ScrapeResultFixed): The envelope containing items.
        payload (ScrapeCreate): Original request (used to log agent mode).

    Returns:
        None

    Notes:
        - Intentionally tolerant to attribute/index errors to avoid noisy failures in logs.
    """
    try:
        items_list = getattr(result_model, "items", [])
        first: dict[str, object] = {}
        if items_list:
            first_item = items_list[0]
            if hasattr(first_item, "model_dump"):
                first = first_item.model_dump()
            elif isinstance(first_item, dict):
                first = first_item
        logger.debug(
            MSG_LOG_DEBUG_DYNAMIC_EXTRAS.format(
                agent_mode=payload.agent_mode,
                keys=sorted(first.keys()),
            )
        )
    except (AttributeError, IndexError, TypeError, ValueError) as e:
        logger.debug(MSG_LOG_DYNAMIC_EXTRAS_ERROR.format(error=e))


def _finalize_success_if_not_canceled(
    job_id: str,
    result_model: ScrapeResultDynamic | ScrapeResultFixed,
) -> None:
    """
    Transition job to SUCCEEDED and persist the result if not already terminal.

    Args:
        job_id (str): The job identifier.
        result_model (ScrapeResultDynamic | ScrapeResultFixed): Final result envelope.

    Returns:
        None

    Notes:
        - Does nothing if the job is already CANCELED/SUCCEEDED/FAILED.
        - Sets progress to 1.0 on success.
    """
    current = get_job(job_id)
    if not current:
        return
    status_lower = str(current.get("status", "")).lower()
    if status_lower in {"canceled", "succeeded", "failed"}:
        # Respect terminal state; do not overwrite
        return

    update_job(
        job_id,
        status=JobStatus.SUCCEEDED,
        result=result_model.model_dump(),
        progress=1.0,
        updated_at=datetime.now(timezone.utc),
    )
    logger.info(MSG_JOB_SUCCEEDED.format(job_id=job_id))


def _finalize_failure(job_id: str, e: Exception) -> None:
    """
    Mark the job as FAILED (if not already terminal) and log the exception.

    Args:
        job_id (str): The job identifier.
        e (Exception): The exception that triggered failure.

    Returns:
        None

    Notes:
        - Preserves the last reported progress value instead of forcing 0.0.
        - Uses a stringified error for the stored `error` field.
    """
    current = get_job(job_id)
    if not current:
        return
    status_lower = str(current.get("status", "")).lower()
    if status_lower in {"canceled", "succeeded", "failed"}:
        logger.debug(MSG_JOB_SKIP_MARK_FAILED_TERMINAL.format(job_id=job_id, status=status_lower))
        return

    # Preserve last progress on failure; don't force to 0.0
    update_job(
        job_id,
        status="failed",
        error=str(e),
        updated_at=datetime.now(timezone.utc),
    )
    logger.exception(MSG_JOB_FAILED.format(job_id=job_id))
