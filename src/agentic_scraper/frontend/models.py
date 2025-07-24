from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class PipelineConfig:
    fetch_concurrency: int
    llm_concurrency: int
    screenshot_enabled: bool
    verbose: bool
    openai_model: str
    agent_mode: str
    retry_attempts: int
    llm_schema_retries: int


class SidebarConfig(BaseModel):
    screenshot_enabled: bool
    fetch_concurrency: int
    llm_concurrency: int
    verbose: bool
    openai_model: str | None  # None if rule-based agent is used
    agent_mode: str  # Enum value as string (e.g. "llm-fixed")
    retry_attempts: int
    llm_schema_retries: int
