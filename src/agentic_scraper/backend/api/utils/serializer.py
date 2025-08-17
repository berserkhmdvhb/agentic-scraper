from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from agentic_scraper.backend.config.messages import MSG_DEBUG_ITEM_SERIALIZATION_FAILED

if TYPE_CHECKING:
    from agentic_scraper.backend.config.aliases import JSONValue

logger = logging.getLogger(__name__)


@runtime_checkable
class _PydanticV2Like(Protocol):
    def model_dump(self) -> dict[str, JSONValue]: ...


@runtime_checkable
class _PydanticV1Like(Protocol):
    def dict(self) -> dict[str, JSONValue]: ...


def to_jsonable_item(item: object) -> dict[str, JSONValue]:
    """
    Convert a single scraped item to a JSON-safe dict.
    Supports Pydantic v2 (model_dump), v1 (dict), or plain dict.
    Falls back to {"value": str(item)} on failure.
    """
    try:
        if isinstance(item, _PydanticV2Like):
            return item.model_dump()
        if isinstance(item, _PydanticV1Like):
            return item.dict()
        if isinstance(item, dict):
            # assume already JSON-safe; caller is responsible for contents
            return item
    except (TypeError, ValueError, AttributeError) as e:
        logger.debug(MSG_DEBUG_ITEM_SERIALIZATION_FAILED.format(error=e))
    return {"value": str(item)}


def serialize_items(items: Iterable[object]) -> list[dict[str, JSONValue]]:
    return [to_jsonable_item(it) for it in items]
