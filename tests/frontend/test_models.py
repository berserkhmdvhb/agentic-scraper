from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from agentic_scraper.backend.config.types import AgentMode, OpenAIModel
from agentic_scraper.frontend.models import PipelineConfig, SidebarConfig

FETCH_CONCURRENCY = 3
LLM_CONCURRENCY = 2
RETRY_ATTEMPTS = 2
LLM_SCHEMA_RETRIES = 1


def _sample_kwargs() -> dict[str, object]:
    return {
        "fetch_concurrency": FETCH_CONCURRENCY,
        "llm_concurrency": LLM_CONCURRENCY,
        "screenshot_enabled": True,
        "verbose": False,
        "openai_model": OpenAIModel.GPT_4O,
        "agent_mode": AgentMode.LLM_DYNAMIC_ADAPTIVE,
        "retry_attempts": RETRY_ATTEMPTS,
        "llm_schema_retries": LLM_SCHEMA_RETRIES,
    }


def test_pipeline_config_valid() -> None:
    cfg = PipelineConfig(**_sample_kwargs())
    assert cfg.fetch_concurrency == FETCH_CONCURRENCY
    assert cfg.llm_concurrency == LLM_CONCURRENCY
    assert cfg.screenshot_enabled is True
    assert cfg.verbose is False
    assert cfg.openai_model is OpenAIModel.GPT_4O
    assert cfg.agent_mode is AgentMode.LLM_DYNAMIC_ADAPTIVE
    assert cfg.retry_attempts == RETRY_ATTEMPTS
    assert cfg.llm_schema_retries == LLM_SCHEMA_RETRIES


def test_pipeline_config_openai_model_none() -> None:
    data = _sample_kwargs()
    data["openai_model"] = None
    cfg = PipelineConfig(**data)
    assert cfg.openai_model is None


def test_sidebar_config_round_trip_json() -> None:
    cfg = SidebarConfig(**_sample_kwargs())
    dumped = cfg.model_dump()
    # JSON round trip should preserve values (enums become values by default)
    loaded = SidebarConfig.model_validate(json.loads(json.dumps(dumped)))
    assert loaded == cfg


def test_invalid_enums_raise_validation_error() -> None:
    bad = _sample_kwargs()
    bad["agent_mode"] = "not-a-real-mode"
    with pytest.raises(ValidationError):
        _ = PipelineConfig(**bad)

    bad2 = _sample_kwargs()
    bad2["openai_model"] = "gpt-magical"
    with pytest.raises(ValidationError):
        _ = SidebarConfig(**bad2)


def test_field_parity_between_pipeline_and_sidebar() -> None:
    pipeline_fields = set(PipelineConfig.model_fields.keys())
    sidebar_fields = set(SidebarConfig.model_fields.keys())
    # Intentionally keep these in lockstep so UI serialization stays simple
    assert pipeline_fields == sidebar_fields
