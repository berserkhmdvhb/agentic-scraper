from agentic_scraper.backend.config.messages import MSG_ERROR_UNHANDLED_AGENT_MODE
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.backend.utils.validators import validate_agent_mode

from .llm_dynamic import extract_structured_data as extract_dynamic
from .llm_dynamic_adaptive import extract_structured_data as extract_dynamic_adaptive
from .llm_fixed import extract_structured_data as extract_fixed
from .rule_based import extract_structured_data as extract_rule_based


async def extract_structured_data(
    text: str,
    url: str,
    *,
    take_screenshot: bool,
    settings: Settings,
) -> ScrapedItem | None:
    mode = validate_agent_mode(settings.agent_mode)

    if mode == AgentMode.LLM_FIXED:
        return await extract_fixed(
            text=text, url=url, take_screenshot=take_screenshot, settings=settings
        )
    if mode == AgentMode.LLM_DYNAMIC:
        return await extract_dynamic(
            text=text, url=url, take_screenshot=take_screenshot, settings=settings
        )
    if mode == AgentMode.LLM_DYNAMIC_ADAPTIVE:
        return await extract_dynamic_adaptive(
            text=text, url=url, take_screenshot=take_screenshot, settings=settings
        )
    if mode == AgentMode.RULE_BASED:
        return await extract_rule_based(
            text=text, url=url, take_screenshot=take_screenshot, settings=settings
        )

    raise ValueError(MSG_ERROR_UNHANDLED_AGENT_MODE.format(value=mode))
