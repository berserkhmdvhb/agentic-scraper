import logging

from agentic_scraper.config.messages import (
    MSG_DEBUG_AGENT_DISPATCH_START,
    MSG_DEBUG_AGENT_SELECTED,
    MSG_ERROR_UNHANDLED_AGENT_MODE,
)
from agentic_scraper.config.models import ScrapedItem, ScrapeRequest
from agentic_scraper.config.types import AgentMode
from agentic_scraper.core.settings import Settings
from agentic_scraper.utils.validators import validate_agent_mode

from .llm_dynamic import extract_structured_data as extract_dynamic
from .llm_dynamic_adaptive import extract_adaptive_data as extract_dynamic_adaptive
from .llm_fixed import extract_structured_data as extract_fixed
from .rule_based import extract_structured_data as extract_rule_based

logger = logging.getLogger(__name__)

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
    mode = validate_agent_mode(settings.agent_mode)
    logger.debug(MSG_DEBUG_AGENT_DISPATCH_START.format(mode=mode))

    agent_fn = AGENT_DISPATCH.get(mode)
    if not agent_fn:
        raise ValueError(MSG_ERROR_UNHANDLED_AGENT_MODE.format(value=mode))

    logger.debug(MSG_DEBUG_AGENT_SELECTED.format(mode=mode))
    return await agent_fn(request, settings=settings)
