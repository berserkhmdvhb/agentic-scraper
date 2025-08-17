from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias, TypedDict

from agentic_scraper.backend.scraper.schemas import ScrapedItem

ScrapeInput: TypeAlias = tuple[str, str]
OnSuccessCallback: TypeAlias = Callable[[ScrapedItem], None]
OnErrorCallback: TypeAlias = Callable[[str, Exception], None]

ScrapeResultWithSkipCount: TypeAlias = tuple[list[ScrapedItem], int]


# JSON-like recursive type (serializable payloads)
JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


class ResultPayload(TypedDict):
    items: list[dict[str, JSONValue]]
    stats: dict[str, float | int | bool]
