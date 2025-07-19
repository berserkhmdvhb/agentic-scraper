# ---------------------------------------------------------------------
# core/
# ---------------------------------------------------------------------

# settings.py

# === OpenAI Models ===
VALID_OPENAI_MODELS = {"gpt-3.5-turbo", "gpt-4", "gpt-4o"}
DEFAULT_OPENAI_MODEL = "gpt-3.5-turbo"


# === Agent / LLM ===
DEFAULT_LLM_MAX_TOKENS = 500
DEFAULT_LLM_TEMPERATURE = 0.0
LLM_TEMPERATURE_MIN = 0.0
LLM_TEMPERATURE_MAX = 2.0
LLM_MAX_TOKENS_LIMIT = 8192  # depends on model but good upper bound

# === Concurrency & Network ===
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_CONCURRENT_REQUESTS = 10
MAX_CONCURRENCY_HARD_LIMIT = 100  # sanity cap for system load

# === Environment Management ===
VALID_ENVIRONMENTS = {"DEV", "UAT", "PROD"}

# === Logging ===
DEFAULT_LOG_MAX_BYTES = 1_000_000
DEFAULT_LOG_BACKUP_COUNT = 5

# === Log Levels ===
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "plain"
VALID_LOG_FORMATS = {"plain", "json"}

# === Screenshot & Log Paths ===
DEFAULT_SCREENSHOT_DIR = "screenshots"
DEFAULT_LOG_DIR = "logs"


# ---------------------------------------------------------------------
# scraper/
# ---------------------------------------------------------------------

# fetcher.py

FETCH_RETRY_ATTEMPTS = 3
FETCH_RETRY_DELAY_SECONDS = 1
