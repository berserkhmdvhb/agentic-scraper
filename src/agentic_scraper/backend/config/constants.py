from agentic_scraper.backend.config.types import (
    AgentMode,
    Auth0Algs,
    Environment,
    LogFormat,
    LogLevel,
    OpenAIModel,
)

SCRAPER_CONFIG_FIELDS = [
    "fetch_concurrency",
    "llm_concurrency",
    "screenshot_enabled",
    "verbose",
    "openai_model",
    "agent_mode",
    "retry_attempts",
    "llm_schema_retries",
]

# ---------------------------------------------------------------------
# frontend/
# ---------------------------------------------------------------------

AUTH0_LOGOUT_PATH = "/v2/logout"


# === Streamlit Session Keys ===
SESSION_KEYS = {
    "agent_mode": "agent_mode",
    "openai_model": "openai_model",
    "fetch_concurrency": "fetch_concurrency",
    "llm_concurrency": "llm_concurrency",
    "screenshot_enabled": "screenshot_enabled",
    "verbose": "verbose",
    "retry_attempts": "retry_attempts",
    "llm_schema_retries": "llm_schema_retries",
}

REQUIRED_CONFIG_FIELDS_FOR_LLM = (
    "openai_model",
    "openai_credentials",
    "llm_concurrency",
    "llm_schema_retries",
)

URL_NUDGE_THRESHOLD = 50
# ---------------------------------------------------------------------
# utils/validators.py
# ---------------------------------------------------------------------

# RFC 4122 defines versions 1, 3, 4, 5;
# newer drafts add 7. Python exposes this as UUID.version (int).
ACCEPTED_UUID_VERSIONS: set[int] = {4}

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
DEFAULT_AGENT_MODE: AgentMode = AgentMode.RULE_BASED
DEFAULT_LLM_TEMPERATURE = 0.3
DEFAULT_LLM_MAX_TOKENS = 1000
LLM_TEMPERATURE_MIN = 0.0
LLM_TEMPERATURE_MAX = 2.0
DEFAULT_LLM_SCHEMA_RETRIES = 2

MIN_LLM_TEMPERATURE = 0.0
MAX_LLM_TEMPERATURE = 2.0

MIN_LLM_MAX_TOKENS = 16
MAX_LLM_MAX_TOKENS = 8192

MIN_RETRY_ATTEMPTS = 0
MAX_RETRY_ATTEMPTS = 10

MIN_LLM_SCHEMA_RETRIES = 0
MAX_LLM_SCHEMA_RETRIES = 10
MIN_MAX_CONCURRENT_REQUESTS = 1


MIN_BACKOFF_SECONDS = 0.1  # for both min and max backoff

# === Concurrency & Network ===
DEFAULT_REQUEST_TIMEOUT = 10
DEFAULT_MAX_CONCURRENT_REQUESTS = 10
MAX_CONCURRENCY_HARD_LIMIT = 100
DEFAULT_RETRY_ATTEMPTS = 2
DEFAULT_RETRY_BACKOFF_MIN = 1.0
DEFAULT_RETRY_BACKOFF_MAX = 10.0

DEFAULT_FETCH_CONCURRENCY = 10
MIN_FETCH_CONCURRENCY = 1
MAX_FETCH_CONCURRENCY = 100

DEFAULT_LLM_CONCURRENCY = 5
MIN_LLM_CONCURRENCY = 1
MAX_LLM_CONCURRENCY = 10

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


# === Security & Authenticaion ===
MIN_ENCRYPTION_SECRET_LENGTH = 32
DEFAULT_AUTH0_ALGORITHM: str = Auth0Algs.RS256.value
VALID_AUTH0_ALGORITHMS: set[str] = {alg.value for alg in Auth0Algs}
# JWT format: header.payload.signature
EXPECTED_JWT_PARTS = 3

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

REGEX_PRICE_PATTERN = r"\$\s?(\d+(?:[\.,]\d{2})?)"
REGEX_PARAGRAPH_SPLIT_PATTERN = r"\n\s*\n"
DESCRIPTION_MIN_LENGTH = 80
DESCRIPTION_MAX_LENGTH = 500
MAX_TEXT_FOR_FEWSHOT = 2000
IMPORTANT_FIELDS = {"title", "job_title", "price", "company", "summary", "description"}
FIELD_SYNONYMS: dict[str, str] = {
    "cost": "price",
    "amount": "price",
    "heading": "title",
    "posted_by": "author",
}


# ---------------------------------------------------------------------
# api/auth/
# ---------------------------------------------------------------------

# dependencies.py

CLAIM_EMAIL = "https://agentic.scraper/email"
CLAIM_NAME = "https://agentic.scraper/name"
