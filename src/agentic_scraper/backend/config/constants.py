from agentic_scraper.backend.config.types import (
    AgentMode,
    Environment,
    LogFormat,
    LogLevel,
    OpenAIModel,
)

# ---------------------------------------------------------------------
# core/
# ---------------------------------------------------------------------

# settings.py
# === Application Identity ===
PROJECT_NAME = "Agentic Scraper"
DEFAULT_VERBOSE: bool = False
DEFAULT_DEBUG_MODE: bool = False

# === Environment Management ===
VALID_ENVIRONMENTS = {env.value for env in Environment}
DEFAULT_ENV: str = Environment.DEV.value

# === Screenshot Toggle ===
DEFAULT_SCREENSHOT_ENABLED = True

# === OpenAI Models ===
VALID_OPENAI_MODELS = {model.value for model in OpenAIModel}
DEFAULT_OPENAI_MODEL: str = OpenAIModel.GPT_3_5.value

VALID_MODEL_OPTIONS = {
    OpenAIModel.GPT_3_5.value: "GPT-3.5 Turbo (Fast + Cheap)",
    OpenAIModel.GPT_3_5_16K.value: "GPT-3.5 Turbo 16k (More context)",
    OpenAIModel.GPT_4.value: "GPT-4 (Slower, costly, very accurate)",
    OpenAIModel.GPT_4O.value: "GPT-4o (Best overall, multimodal, fast)",
}

# === Agent / LLM ===
VALID_AGENT_MODES = {mode.value for mode in AgentMode}
DEFAULT_AGENT_MODE: str = AgentMode.LLM_FIXED.value

DEFAULT_LLM_TEMPERATURE = 0.3
DEFAULT_LLM_MAX_TOKENS = 1000
LLM_TEMPERATURE_MIN = 0.0
LLM_TEMPERATURE_MAX = 2.0
LLM_MAX_TOKENS_LIMIT = 8192  # depends on model but good upper bound

# === Concurrency & Network ===
DEFAULT_REQUEST_TIMEOUT = 10
DEFAULT_MAX_CONCURRENT_REQUESTS = 10
MAX_CONCURRENCY_HARD_LIMIT = 100
DEFAULT_RETRY_ATTEMPTS = 2
DEFAULT_RETRY_BACKOFF_MIN = 1.0
DEFAULT_RETRY_BACKOFF_MAX = 10.0

# === Logging ===
DEFAULT_LOG_MAX_BYTES = 1_000_000
DEFAULT_LOG_BACKUP_COUNT = 5

VALID_LOG_LEVELS = {lvl.value for lvl in LogLevel}
DEFAULT_LOG_LEVEL: str = LogLevel.INFO.value

VALID_LOG_FORMATS = {fmt.value for fmt in LogFormat}
DEFAULT_LOG_FORMAT: str = LogFormat.PLAIN.value

# === Screenshot & Log Paths ===
DEFAULT_SCREENSHOT_DIR = "screenshots"
DEFAULT_LOG_DIR = "logs"

# logger_setup.py
LOGGER_NAME = "agentic_scraper"
DEFAULT_DUMP_LLM_JSON_DIR = "./.cache/llm_dumps"

# ---------------------------------------------------------------------
# scraper/
# ---------------------------------------------------------------------

# fetcher.py
FETCH_RETRY_ATTEMPTS = 3
FETCH_RETRY_DELAY_SECONDS = 1
FETCH_ERROR_PREFIX = "__FETCH_ERROR__"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ---------------------------------------------------------------------
# scraper/agent/
# ---------------------------------------------------------------------

# Regex Patterns
REGEX_PRICE_PATTERN = r"\$\s?(\d+(?:[\.,]\d{2})?)"
REGEX_PARAGRAPH_SPLIT_PATTERN = r"\n\s*\n"

# Description length constraints
DESCRIPTION_MIN_LENGTH = 80
DESCRIPTION_MAX_LENGTH = 500
