from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.models import ScrapedItem


async def extract_structured_data(
    text: str,
    url: str,
    *,
    take_screenshot: bool,
    settings: Settings,
) -> ScrapedItem | None:
    message = "llm_dynamic_adaptive agent is not implemented yet."
    raise NotImplementedError(message)
