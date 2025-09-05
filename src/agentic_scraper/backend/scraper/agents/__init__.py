# src/agentic_scraper/backend/scraper/agents/__init__.py
"""
Unified agent dispatcher for structured data extraction.

Responsibilities:
- Map `AgentMode` values to the appropriate extraction function.
- Provide a single public entrypoint `extract_structured_data` that selects and
  invokes the right agent (rule-based, fixed LLM, dynamic LLM, adaptive LLM).

Public API:
- `extract_structured_data`: Unified async function that delegates to the agent
  selected by `settings.agent_mode`.

Operational:
- Logging: DEBUG-level logs for dispatch start/selection.
- Errors: Raises `ValueError` if the `AgentMode` is unrecognized.

Usage:
    from agentic_scraper.backend.scraper import agents
    item = await agents.extract_structured_data(request, settings=settings)

Notes:
- Each agent function is imported under a local alias (e.g., `extract_fixed`) to
  make dispatch explicit and testable.
"""

import logging

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_AGENT_DISPATCH_START,
    MSG_DEBUG_AGENT_SELECTED,
    MSG_ERROR_UNHANDLED_AGENT_MODE,
)
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.models import ScrapeRequest
from agentic_scraper.backend.scraper.schemas import ScrapedItem
from agentic_scraper.backend.utils.validators import validate_agent_mode

# Import agent-specific extractors under short aliases for dispatch.
from .llm_dynamic import extract_structured_data as extract_dynamic
from .llm_dynamic_adaptive import extract_adaptive_data as extract_dynamic_adaptive
from .llm_fixed import extract_structured_data as extract_fixed
from .rule_based import extract_structured_data as extract_rule_based

logger = logging.getLogger(__name__)

__all__ = ["extract_structured_data"]

# Agent dispatch table — maps AgentMode enum values to implementation functions.
AGENT_DISPATCH = {
    AgentMode.LLM_FIXED: extract_fixed,
    AgentMode.LLM_DYNAMIC: extract_dynamic,
    AgentMode.LLM_DYNAMIC_ADAPTIVE: extract_dynamic_adaptive,
    AgentMode.RULE_BASED: extract_rule_based,
}


async def extract_structured_data(
    request: ScrapeRequest,
    *,
    settings: Settings,
) -> ScrapedItem | None:
    """
    Unified agent entrypoint for structured data extraction.

    Args:
        request (ScrapeRequest): Input containing URL, cleaned text, and context.
        settings (Settings): Runtime settings, including `agent_mode` and OpenAI config.

    Returns:
        ScrapedItem | None: Structured item if extraction succeeds; None if the agent
            produces no valid result.

    Raises:
        ValueError: If `settings.agent_mode` is invalid or unhandled.

    Notes:
        - Logs dispatch start and selected agent at DEBUG level.
        - Calls into the appropriate agent implementation and returns its result.
    """
    mode = validate_agent_mode(settings.agent_mode)
    logger.debug(MSG_DEBUG_AGENT_DISPATCH_START.format(mode=mode))

    agent_fn = AGENT_DISPATCH.get(mode)
    if not agent_fn:
        # Defensive: If a new AgentMode is added but not mapped, fail fast.
        raise ValueError(MSG_ERROR_UNHANDLED_AGENT_MODE.format(value=mode))

    logger.debug(MSG_DEBUG_AGENT_SELECTED.format(mode=mode))
    return await agent_fn(request, settings=settings)
