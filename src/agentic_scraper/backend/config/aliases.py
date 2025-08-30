from collections.abc import Callable
from typing import TypeAlias

import httpx
from openai import APIError as _APIError
from openai import OpenAIError as _OpenAIError
from openai import RateLimitError as _RateLimitError

from agentic_scraper.backend.scraper.schemas import ScrapedItem

ScrapeInput: TypeAlias = tuple[str, str]
OnSuccessCallback: TypeAlias = Callable[[ScrapedItem], None]
OnErrorCallback: TypeAlias = Callable[[str, Exception], None]

ScrapeResultWithSkipCount: TypeAlias = tuple[list[ScrapedItem], int]

AsyncClientFactory = Callable[..., httpx.AsyncClient]

OpenAIErrorT = _OpenAIError
APIErrorT = _APIError
RateLimitErrorT = _RateLimitError
