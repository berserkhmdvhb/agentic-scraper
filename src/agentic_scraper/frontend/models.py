from pydantic import BaseModel

from agentic_scraper.config.types import AgentMode, OpenAIModel


class PipelineConfig(BaseModel):
    fetch_concurrency: int
    llm_concurrency: int
    screenshot_enabled: bool
    verbose: bool
    openai_model: OpenAIModel | None
    agent_mode: AgentMode
    retry_attempts: int
    llm_schema_retries: int


class SidebarConfig(BaseModel):
    screenshot_enabled: bool
    fetch_concurrency: int
    llm_concurrency: int
    verbose: bool
    openai_model: OpenAIModel | None
    agent_mode: AgentMode
    retry_attempts: int
    llm_schema_retries: int
