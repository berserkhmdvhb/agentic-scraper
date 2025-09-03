from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CancelToken:
    """Composable cancel primitive used across scraper modules."""

    event: asyncio.Event | None = None
    should_cancel: Callable[[], bool] | None = None


def safe_should_cancel(fn: Callable[[], bool] | None) -> bool:
    """Evaluate a user-supplied cancel predicate safely."""
    if fn is None:
        return False
    try:
        return bool(fn())
    except Exception as e:  # noqa: BLE001
        logger.debug("should_cancel predicate raised: %r", e)
        return False


def is_canceled(token: CancelToken | None) -> bool:
    """True iff the token's event is set or its predicate returns True."""
    if token is None:
        return False
    if token.event and token.event.is_set():
        return True
    return safe_should_cancel(token.should_cancel)


def raise_if_canceled(token: CancelToken | None) -> None:
    """Raise asyncio.CancelledError when the token indicates cancellation."""
    if is_canceled(token):
        raise asyncio.CancelledError
