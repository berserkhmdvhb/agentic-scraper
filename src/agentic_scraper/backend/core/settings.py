import logging

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # General
    project_name: str = "Agentic Scraper"
    debug_mode: bool = Field(default=False, env="DEBUG")
    env: str = Field(default="dev", env="ENV")

    # OpenAI
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-3.5-turbo")
    openai_project_id: str | None = Field(default=None, env="OPENAI_PROJECT_ID")

    # Network
    request_timeout: int = Field(default=10, description="HTTP request timeout in seconds")
    max_concurrent_requests: int = Field(
        default=10, env="MAX_CONCURRENT_REQUESTS", description="Max simultaneous fetches"
    )

    # Agent behavior
    llm_max_tokens: int = Field(default=500, env="LLM_MAX_TOKENS")
    llm_temperature: float = Field(default=0.0, env="LLM_TEMPERATURE")

    @model_validator(mode="after")
    def validate_config(self) -> "Settings":
        logger.debug("Loaded settings: %s", self.model_dump())
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required in your .env file.")

        # Custom log summary
        logger.debug("Using model: %s", self.openai_model)
        logger.debug("Max tokens: %d", self.llm_max_tokens)
        logger.debug("Temperature: %.2f", self.llm_temperature)
        logger.debug("OpenAI key loaded with prefix: %s", self.openai_api_key[:8])
        logger.debug("Using project ID: %s", self.openai_project_id)

        logger.debug("Environment: %s", self.env)
        logger.debug("Debug mode: %s", self.debug_mode)
        logger.debug("Model: %s", self.openai_model)
        logger.debug("Tokens: %d", self.llm_max_tokens)
        logger.debug("Temperature: %.2f", self.llm_temperature)
        logger.debug("Concurrency: %d", self.max_concurrent_requests)

        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
