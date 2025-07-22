from agentic_scraper.backend.config.aliases import (
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

# === Environment Management ===
VALID_ENVIRONMENTS = {"DEV", "UAT", "PROD"}
DEFAULT_ENV: Environment = "DEV"

# === Screenshot Toggle ===
DEFAULT_SCREENSHOT_ENABLED = True

# === OpenAI Models ===
VALID_OPENAI_MODELS = {"gpt-3.5-turbo", "gpt-4", "gpt-4o"}
DEFAULT_OPENAI_MODEL: OpenAIModel = "gpt-3.5-turbo"

# === Agent / LLM ===
DEFAULT_LLM_MAX_TOKENS = 500
DEFAULT_LLM_TEMPERATURE = 0.0
LLM_TEMPERATURE_MIN = 0.0
LLM_TEMPERATURE_MAX = 2.0
LLM_MAX_TOKENS_LIMIT = 8192  # depends on model but good upper bound

# === Concurrency & Network ===
DEFAULT_REQUEST_TIMEOUT = 10
DEFAULT_MAX_CONCURRENT_REQUESTS = 10
MAX_CONCURRENCY_HARD_LIMIT = 100  # sanity cap for system load

# === Logging ===
DEFAULT_LOG_MAX_BYTES = 1_000_000
DEFAULT_LOG_BACKUP_COUNT = 5

# === Log Levels ===
DEFAULT_LOG_LEVEL: LogLevel = "INFO"
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
DEFAULT_LOG_FORMAT: LogFormat = "plain"
VALID_LOG_FORMATS = {"plain", "json"}

# === Screenshot & Log Paths ===
DEFAULT_SCREENSHOT_DIR = "screenshots"
DEFAULT_LOG_DIR = "logs"

# logger_setup.py
LOGGER_NAME = "agentic_scraper"

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
