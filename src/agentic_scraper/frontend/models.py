"""
Configuration schemas for the Streamlit frontend.

Models:
- `PipelineConfig`: Full pipeline execution settings, including retries and schema retries.
- `SidebarConfig`: UI-bound subset of pipeline configuration, reflecting sidebar controls.

Serialization:
- Both classes are Pydantic `BaseModel`s; they support `.model_dump()` for JSON serialization.
- Optional fields (`openai_model`) serialize as `null` if not set.

Validation & Defaults:
- No default values are provided here; values are expected to be set by the UI or caller.
- Type checking ensures correct enum usage for `AgentMode` and `OpenAIModel`.

Usage:
    from agentic_scraper.frontend.models import PipelineConfig

    config = PipelineConfig(
        fetch_concurrency=5,
        llm_concurrency=3,
        screenshot_enabled=True,
        verbose=False,
        openai_model=OpenAIModel.GPT_4,
        agent_mode=AgentMode.LLM_DYNAMIC,
        retry_attempts=2,
        llm_schema_retries=1,
    )
    payload = config.model_dump()

Notes:
- `PipelineConfig` represents the full scraping run configuration passed to the backend.
- `SidebarConfig` mirrors the sidebar UI state, which is then transformed into a `PipelineConfig`
  before invoking the backend.
"""

from pydantic import BaseModel

from agentic_scraper.backend.config.types import AgentMode, OpenAIModel


class PipelineConfig(BaseModel):
    """
    Execution settings for a scraping pipeline.

    Attributes:
        fetch_concurrency (int): Max concurrent network fetches.
        llm_concurrency (int): Max concurrent LLM calls.
        screenshot_enabled (bool): Whether screenshots are captured.
        verbose (bool): If True, enable verbose logging.
        openai_model (OpenAIModel | None): Which OpenAI model to use (or None).
        agent_mode (AgentMode): Agent selection strategy (LLM-based, rule-based, etc.).
        retry_attempts (int): Number of retries for network/agent failures.
        llm_schema_retries (int): Max schema retries for adaptive LLM agents.

    Notes:
        - Typically constructed from sidebar config before dispatching to the backend.
    """

    fetch_concurrency: int
    llm_concurrency: int
    screenshot_enabled: bool
    verbose: bool
    openai_model: OpenAIModel | None
    agent_mode: AgentMode
    retry_attempts: int
    llm_schema_retries: int


class SidebarConfig(BaseModel):
    """
    Sidebar UI state that mirrors pipeline configuration.

    Attributes:
        screenshot_enabled (bool): Whether screenshots are captured.
        fetch_concurrency (int): Max concurrent network fetches.
        llm_concurrency (int): Max concurrent LLM calls.
        verbose (bool): If True, enable verbose logging.
        openai_model (OpenAIModel | None): Which OpenAI model to use (or None).
        agent_mode (AgentMode): Agent selection strategy (LLM-based, rule-based, etc.).
        retry_attempts (int): Number of retries for network/agent failures.
        llm_schema_retries (int): Max schema retries for adaptive LLM agents.

    Notes:
        - This schema represents UI controls, not necessarily what is passed directly
          to the backend. It may be transformed into `PipelineConfig` before use.
    """

    screenshot_enabled: bool
    fetch_concurrency: int
    llm_concurrency: int
    verbose: bool
    openai_model: OpenAIModel | None
    agent_mode: AgentMode
    retry_attempts: int
    llm_schema_retries: int
