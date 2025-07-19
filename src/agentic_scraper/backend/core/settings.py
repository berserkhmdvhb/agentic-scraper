import logging

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_API_KEY_PREFIX,
    MSG_DEBUG_CONCURRENCY,
    MSG_DEBUG_DEBUG_MODE,
    MSG_DEBUG_ENVIRONMENT,
    MSG_DEBUG_MAX_TOKENS,
    MSG_DEBUG_PROJECT_ID,
    MSG_DEBUG_SETTINGS_LOADED,
    MSG_DEBUG_TEMPERATURE,
    MSG_DEBUG_USING_MODEL,
    MSG_ERROR_MISSING_API_KEY,
)

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # General
    project_name: str = "Agentic Scraper"
    debug_mode: bool = Field(default=False, validation_alias="DEBUG")
    env: str = Field(default="dev", validation_alias="ENV")

    # OpenAI
    openai_api_key: str = Field(..., validation_alias="OPENAI_API_KEY")
    openai_model: str = "gpt-3.5-turbo"
    openai_project_id: str | None = Field(default=None, validation_alias="OPENAI_PROJECT_ID")

    # Network
    request_timeout: int = 10
    max_concurrent_requests: int = Field(
        default=10,
        validation_alias="MAX_CONCURRENT_REQUESTS",
        description="Max simultaneous fetches",
    )

    # Agent behavior
    llm_max_tokens: int = Field(default=500, validation_alias="LLM_MAX_TOKENS")
    llm_temperature: float = Field(default=0.0, validation_alias="LLM_TEMPERATURE")

    # Screenshotting
    screenshot_enabled: bool = Field(default=True, validation_alias="SCREENSHOT_ENABLED")
    screenshot_dir: str = Field(default="screenshots", validation_alias="SCREENSHOT_DIR")

    @model_validator(mode="after")
    def validate_config(self) -> "Settings":
        logger.debug(MSG_DEBUG_SETTINGS_LOADED, self.model_dump())

        if not self.openai_api_key:
            raise ValueError(MSG_ERROR_MISSING_API_KEY)

        logger.debug(MSG_DEBUG_USING_MODEL, self.openai_model)
        logger.debug(MSG_DEBUG_MAX_TOKENS, self.llm_max_tokens)
        logger.debug(MSG_DEBUG_TEMPERATURE, self.llm_temperature)
        logger.debug(MSG_DEBUG_API_KEY_PREFIX, self.openai_api_key[:8])
        logger.debug(MSG_DEBUG_PROJECT_ID, self.openai_project_id)

        logger.debug(MSG_DEBUG_ENVIRONMENT, self.env)
        logger.debug(MSG_DEBUG_DEBUG_MODE, self.debug_mode)
        logger.debug(MSG_DEBUG_CONCURRENCY, self.max_concurrent_requests)

        return self

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
