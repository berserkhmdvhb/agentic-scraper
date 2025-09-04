from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

import agentic_scraper.backend.scraper.agents as agents_mod
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_AGENT_DISPATCH_START,
    MSG_DEBUG_AGENT_SELECTED,
)
from agentic_scraper.backend.config.types import AgentMode
from agentic_scraper.backend.scraper.agents import extract_structured_data as extract_entry

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

    from agentic_scraper.backend.core.settings import Settings
    from agentic_scraper.backend.scraper.models import ScrapeRequest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    [
        AgentMode.LLM_FIXED,
        AgentMode.LLM_DYNAMIC,
        AgentMode.LLM_DYNAMIC_ADAPTIVE,
        AgentMode.RULE_BASED,
    ],
)
async def test_dispatch_calls_correct_agent_function(
    mode: AgentMode, settings: Settings, monkeypatch: MonkeyPatch
) -> None:
    cfg = settings.model_copy(update={"agent_mode": mode})

    called: dict[str, int] = {"fixed": 0, "dyn": 0, "adaptive": 0, "rule": 0}

    async def _fixed(_req: object, *, settings: Settings) -> dict[str, str]:
        _ = settings
        called["fixed"] += 1
        return {"agent": "fixed"}

    async def _dyn(_req: object, *, settings: Settings) -> dict[str, str]:
        _ = settings
        called["dyn"] += 1
        return {"agent": "dynamic"}

    async def _adaptive(_req: object, *, settings: Settings) -> dict[str, str]:
        _ = settings
        called["adaptive"] += 1
        return {"agent": "adaptive"}

    async def _rule(_req: object, *, settings: Settings) -> dict[str, str]:
        _ = settings
        called["rule"] += 1
        return {"agent": "rule"}

    dispatch = {
        AgentMode.LLM_FIXED: _fixed,
        AgentMode.LLM_DYNAMIC: _dyn,
        AgentMode.LLM_DYNAMIC_ADAPTIVE: _adaptive,
        AgentMode.RULE_BASED: _rule,
    }
    monkeypatch.setattr(agents_mod, "AGENT_DISPATCH", dispatch, raising=True)
    monkeypatch.setattr(agents_mod, "validate_agent_mode", lambda v: v, raising=True)

    # Satisfy the type checker: extract_entry expects ScrapeRequest
    req = cast("ScrapeRequest", object())
    result = await extract_entry(req, settings=cfg)

    expected_key = {
        AgentMode.LLM_FIXED: "fixed",
        AgentMode.LLM_DYNAMIC: "dyn",
        AgentMode.LLM_DYNAMIC_ADAPTIVE: "adaptive",
        AgentMode.RULE_BASED: "rule",
    }[mode]

    assert called[expected_key] == 1
    # Avoid union/dict comparison warning by asserting type first
    assert isinstance(result, dict)
    assert result == {
        "agent": {"fixed": "fixed", "dyn": "dynamic", "adaptive": "adaptive", "rule": "rule"}[
            expected_key
        ]
    }


@pytest.mark.asyncio
async def test_unhandled_mode_raises_value_error(
    settings: Settings, monkeypatch: MonkeyPatch
) -> None:
    cfg = settings.model_copy(update={"agent_mode": AgentMode.LLM_FIXED})
    monkeypatch.setattr(agents_mod, "AGENT_DISPATCH", {}, raising=True)
    monkeypatch.setattr(agents_mod, "validate_agent_mode", lambda v: v, raising=True)

    req = cast("ScrapeRequest", object())
    with pytest.raises(ValueError, match=r"Unhandled AGENT_MODE"):
        await extract_entry(req, settings=cfg)


@pytest.mark.asyncio
async def test_debug_logging_occurs(settings: Settings, monkeypatch: MonkeyPatch) -> None:
    """
    Verify the module emits the expected debug messages by checking for the
    exact formatted strings derived from the message constants.
    """
    cfg = settings.model_copy(update={"agent_mode": AgentMode.RULE_BASED})

    async def _rule(_req: object, *, settings: Settings) -> dict[str, str]:
        _ = settings
        return {"agent": "rule"}

    # Patch dispatch and validator to control the path deterministically
    monkeypatch.setattr(agents_mod, "AGENT_DISPATCH", {AgentMode.RULE_BASED: _rule}, raising=True)
    monkeypatch.setattr(agents_mod, "validate_agent_mode", lambda v: v, raising=True)

    # Fake logger that records debug calls
    class _FakeLogger:
        def __init__(self) -> None:
            self.debug_calls: list[str] = []

        def debug(self, msg: object, *args: object, **kwargs: object) -> None:  # noqa: ARG002
            self.debug_calls.append(str(msg))

    fake_logger = _FakeLogger()
    monkeypatch.setattr(agents_mod, "logger", fake_logger, raising=True)

    # Execute
    req = cast("ScrapeRequest", object())
    _ = await extract_entry(req, settings=cfg)

    # Build the exact messages the module should emit
    expected_start = MSG_DEBUG_AGENT_DISPATCH_START.format(mode=AgentMode.RULE_BASED)
    expected_selected = MSG_DEBUG_AGENT_SELECTED.format(mode=AgentMode.RULE_BASED)

    assert expected_start in fake_logger.debug_calls
    assert expected_selected in fake_logger.debug_calls
