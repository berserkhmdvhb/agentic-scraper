from collections.abc import Callable
from typing import TypeAlias

from agentic_scraper.backend.scraper.models import ScrapedItem

# ---------------------------------------------------------------------
# scraper/
# ---------------------------------------------------------------------

# worker_pool.py
ScrapeInput: TypeAlias = tuple[str, str]
OnSuccessCallback: TypeAlias = Callable[[ScrapedItem], None]
OnErrorCallback: TypeAlias = Callable[[str, Exception], None]

# ---------------------------------------------------------------------
# frontend/app.py
# ---------------------------------------------------------------------

ScrapeResultWithSkipCount: TypeAlias = tuple[list[ScrapedItem], int]
