from enum import Enum

from pydantic import BaseModel

# Enum Classes


class Environment(str, Enum):
    DEV = "DEV"
    UAT = "UAT"
    PROD = "PROD"


class OpenAIModel(str, Enum):
    GPT_3_5 = "gpt-3.5-turbo"
    GPT_3_5_16K = "gpt-3.5-turbo-16k"
    GPT_4 = "gpt-4"
    GPT_4O = "gpt-4o"


class AgentMode(str, Enum):
    LLM_FIXED = "llm-fixed"
    LLM_DYNAMIC = "llm-dynamic"
    LLM_DYNAMIC_ADAPTIVE = "llm-dynamic-adaptive"
    RULE_BASED = "rule-based"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    PLAIN = "plain"
    JSON = "json"


class Auth0Algs(str, Enum):
    RS256 = "RS256"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class OpenAIConfig(BaseModel):
    """
    Container for OpenAI credential configuration used by agents.

    Fields:
        api_key (str | None): API key if provided per-request.
        project_id (str | None): Project ID if provided per-request.
    """

    api_key: str | None = None
    project_id: str | None = None
