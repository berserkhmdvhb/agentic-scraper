from collections.abc import Callable
from typing import TypeAlias

from agentic_scraper.backend.scraper.schemas import ScrapedItem

ScrapeInput: TypeAlias = tuple[str, str]
OnSuccessCallback: TypeAlias = Callable[[ScrapedItem], None]
OnErrorCallback: TypeAlias = Callable[[str, Exception], None]

ScrapeResultWithSkipCount: TypeAlias = tuple[list[ScrapedItem], int]
