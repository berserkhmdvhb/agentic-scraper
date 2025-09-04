"""
Composable cancellation primitives for scraper orchestration.

Responsibilities:
- Provide a lightweight, uniform token (`CancelToken`) that combines both
  an asyncio.Event and a user-supplied cancel predicate.
- Centralize safe evaluation of cancel predicates, shielding the pipeline
  from unexpected exceptions.
- Offer convenience helpers to test or raise cancellation in long-running loops.

Public API:
- `CancelToken`: Immutable container with optional `event` and `should_cancel` callable.
- `safe_should_cancel`: Evaluate a user-supplied cancel predicate safely.
- `is_canceled`: Return True if either the token's event is set or its predicate returns True.
- `raise_if_canceled`: Raise asyncio.CancelledError if the token indicates cancellation.

Usage:
    from agentic_scraper.backend.scraper.cancel_helpers import CancelToken, is_canceled

    token = CancelToken(event=my_event, should_cancel=lambda: check_some_flag())
    if is_canceled(token):
        break  # cooperative cancel
    raise_if_canceled(token)  # raises asyncio.CancelledError if canceled

Notes:
- Prefer `raise_if_canceled` in loops to ensure tasks exit promptly.
- Logging for predicate errors is done at DEBUG level to avoid log spam.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["CancelToken", "is_canceled", "raise_if_canceled", "safe_should_cancel"]


@dataclass(frozen=True)
class CancelToken:
    """
    Composable cancel primitive used across scraper modules.

    Attributes:
        event (asyncio.Event | None): Event that, when set, signals cancellation.
        should_cancel (Callable[[], bool] | None): Predicate that returns True if canceled.
    """

    event: asyncio.Event | None = None
    should_cancel: Callable[[], bool] | None = None


def safe_should_cancel(fn: Callable[[], bool] | None) -> bool:
    """
    Evaluate a user-supplied cancel predicate safely.

    Args:
        fn (Callable[[], bool] | None): Cancel predicate to evaluate.

    Returns:
        bool: True if predicate evaluates to truthy; False on errors or if None.

    Notes:
        - Any exceptions from the predicate are caught and logged at DEBUG level.
        - This ensures cancel checks never crash the caller.
    """
    if fn is None:
        return False
    try:
        return bool(fn())
    except Exception as e:  # noqa: BLE001
        logger.debug("should_cancel predicate raised: %r", e)
        return False


def is_canceled(token: CancelToken | None) -> bool:
    """
    Determine whether a token indicates cancellation.

    Args:
        token (CancelToken | None): Token to check.

    Returns:
        bool: True if the token's event is set or its predicate returns True.
    """
    if token is None:
        return False
    if token.event and token.event.is_set():
        return True
    return safe_should_cancel(token.should_cancel)


def raise_if_canceled(token: CancelToken | None) -> None:
    """
    Raise asyncio.CancelledError when the token indicates cancellation.

    Args:
        token (CancelToken | None): Token to check.

    Raises:
        asyncio.CancelledError: If the token indicates cancellation.
    """
    if is_canceled(token):
        raise asyncio.CancelledError
