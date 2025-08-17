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
    MSG_DEBUG_FINALIZE_SUCCESS_SKIPPED,
    MSG_DEBUG_SCRAPE_CONFIG_MERGED,
    MSG_HTTP_MISSING_OPENAI_CREDS,
    MSG_INFO_INLINE_KEY_MASKED_FALLBACK,
    MSG_JOB_FAILED,
    MSG_JOB_SKIP_MARK_FAILED_TERMINAL,
    MSG_JOB_SKIP_MARK_RUNNING_TERMINAL,
    MSG_JOB_STARTED,
    MSG_LOG_DEBUG_DYNAMIC_EXTRAS,
    MSG_LOG_DYNAMIC_EXTRAS_ERROR,
)
from agentic_scraper.backend.config.types import AgentMode, JobStatus, OpenAIConfig
from agentic_scraper.backend.core.settings import Settings, get_settings
from agentic_scraper.backend.scraper.pipeline import PipelineOptions, scrape_with_stats

logger = logging.getLogger(__name__)
settings = get_settings()


def _masked(s: str | None) -> bool:
    if not s:
        return False
    return any(ch in s for ch in ("*", "•", "●", "·"))


def _mark_running(job_id: str) -> None:
    """Set job to RUNNING and log start."""
    current = get_job(job_id)
    if not current:
        return
    status_val = current.get("status")
    if status_val in {JobStatus.CANCELED, JobStatus.SUCCEEDED, JobStatus.FAILED}:
        logger.debug(MSG_JOB_SKIP_MARK_RUNNING_TERMINAL.format(job_id=job_id, status=status_val))
        return
    update_job(job_id, status=JobStatus.RUNNING, updated_at=datetime.now(timezone.utc))
    logger.info(MSG_JOB_STARTED.format(job_id=job_id))


def _resolve_openai_creds_or_fail(
    job_id: str,
    payload: ScrapeCreate,
    user: AuthUser,
) -> OpenAIConfig | None:
    """
    Resolve OpenAI credentials for this run.

    - If inline creds are masked, ignore them and fall back to stored creds.
    - If agent mode requires LLM and no creds are available, mark job FAILED and return None.
    """
    inline = payload.openai_credentials
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
    """Merge request-provided config fields into the global settings clone and log."""
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
    Execute the scrape pipeline and convert to the correct result model
    (fixed schema vs dynamic).
    """
    urls = [str(u) for u in payload.urls]

    # Expose a store-backed should_cancel() to handle cross-process events/races
    def _should_cancel() -> bool:
        j = get_job(job_id)
        # Fallback: rely on cancel_event if job lookup isn't available
        if j is None:
            return bool(cancel_event and cancel_event.is_set())
        return j.get("status") == JobStatus.CANCELED

    items, stats = await scrape_with_stats(
        urls,
        settings=merged_settings,
        openai=creds,
        options=PipelineOptions(
            cancel_event=cancel_event,
            should_cancel=_should_cancel,
            job_hooks=None,
            job_id=job_id,
        ),
    )

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
    """Best-effort debug log of dynamic extras on the first item."""
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
) -> None:
    """
    No-op: finalization moved to the pipeline (which also respects CANCELED).
    Kept for backward compatibility.
    """
    logger.debug(MSG_DEBUG_FINALIZE_SUCCESS_SKIPPED.format(job_id=job_id))


def _finalize_failure(job_id: str, e: Exception) -> None:
    """Mark job FAILED and log exception with traceback."""
    current = get_job(job_id)
    if not current:
        return
    status_val = current.get("status")
    if status_val in {JobStatus.CANCELED, JobStatus.SUCCEEDED, JobStatus.FAILED}:
        logger.debug(MSG_JOB_SKIP_MARK_FAILED_TERMINAL.format(job_id=job_id, status=status_val))
        return
    # Preserve last progress on failure; don't force to 0.0
    update_job(
        job_id,
        status=JobStatus.FAILED,
        error=str(e),
        updated_at=datetime.now(timezone.utc),
    )
    logger.exception(MSG_JOB_FAILED.format(job_id=job_id))
