# frontend/app.py
MSG_INFO_FETCHING_URLS = "Fetching and processing {} URLs"
MSG_INFO_EXTRACTION_COMPLETE = "Completed extraction for {} URLs"
MSG_INFO_FETCH_SKIPPED = "Skipped %d URLs due to fetch errors"

# ---------------------------------------------------------------------
# core/
# ---------------------------------------------------------------------

# settings.py
MSG_DEBUG_SETTINGS_LOADED = "Loaded settings: %s"
MSG_ERROR_MISSING_API_KEY = "OPENAI_API_KEY is required in your .env file."
MSG_ERROR_INVALID_MODEL_NAME = "Invalid OpenAI model: {model}. Valid options: {valid_options}"
MSG_ERROR_INVALID_TEMPERATURE = "Temperature must be between 0.0 and 2.0. Got: {value}"
MSG_ERROR_INVALID_TOKENS = "Max tokens must be a positive integer. Got: {value}"
MSG_ERROR_INVALID_CONCURRENCY = "Concurrency must be greater than 0. Got: {value}"
MSG_ERROR_INVALID_TIMEOUT = "Request timeout must be greater than 0 seconds. Got: {value}"
MSG_ERROR_INVALID_LOG_LEVEL = "Invalid log level: {value}. Valid options: {valid_options}"
MSG_ERROR_INVALID_LOG_BYTES = "Log max bytes must be greater than 0. Got: {value}"
MSG_ERROR_INVALID_BACKUP_COUNT = "Log backup count must be greater than 0. Got: {value}"
MSG_ERROR_INVALID_ENV = "Invalid environment: {value}. Valid options: {valid_options}"

# settings_helpers.py
MSG_DEBUG_SETTING_OVERRIDDEN = "Overridden {key} = {validated!r} (from env: {original!r})"
MSG_DEBUG_SETTING_SKIPPED = "Skipping {key}: blank or unset → using default"
MSG_WARNING_SETTING_INVALID = "Invalid {key}={original!r}: {error}"

# parallel.py
MSG_ERROR_TASK_FAILED = "Task {idx} failed: {error}"
MSG_ERROR_PARALLEL_TASK_ABORTED = "Parallel task {idx} failed"
MSG_ERROR_RAY_NOT_INSTALLED = (
    "Ray is not installed. Please install with `pip install 'ray[default]'` "
    "on Python < 3.13 to use distributed parallelism."
)
MSG_ERROR_RAY_EXECUTION_FAILED = "Ray-based parallel execution failed"
MSG_ERROR_RAY_RUNTIME_FAILED = "Ray parallel execution failed"
# ---------------------------------------------------------------------
# scraper/
# ---------------------------------------------------------------------

# agent.py
MSG_SYSTEM_PROMPT = """You are a web extraction assistant.
Your job is to extract key data from webpage content.
Return only a JSON object with the following fields:
- title (string or null)
- description (string or null)
- price (float or null)
- author (string or null)
- date_published (string or null)

All values must be valid JSON. If a field is not found, return null for it."""
MSG_ERROR_LLM_RESPONSE_MALFORMED_WITH_URL = "LLM response missing or malformed. [URL: %s]"
MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL = "LLM response was None. [URL: %s]"
MSG_ERROR_JSON_DECODING_FAILED_WITH_URL = "Failed to parse LLM output: %s [URL: %s]"
MSG_ERROR_SCREENSHOT_FAILED_WITH_URL = "Failed to capture screenshot. [URL: %s]"
MSG_ERROR_RATE_LIMIT_LOG_WITH_URL = "OpenAI rate limit exceeded. [URL: %s]"
MSG_ERROR_RATE_LIMIT_DETAIL = "Rate limit detail: %s"
MSG_ERROR_API_LOG_WITH_URL = "OpenAI API error occurred. [URL: %s]"
MSG_ERROR_OPENAI_UNEXPECTED_LOG_WITH_URL = "Unexpected OpenAI error. [URL: %s]"
MSG_ERROR_RATE_LIMIT = (
    "OpenAI quota exceeded. Please check your usage and billing at "
    "https://platform.openai.com/account/usage."
)
MSG_ERROR_RATE_LIMIT_LOG = "OpenAI quota exceeded."
MSG_ERROR_API = "OpenAI API error occurred: {error}"
MSG_ERROR_API_LOG = "OpenAI API error occurred: {}"
MSG_ERROR_OPENAI_UNEXPECTED = "Unexpected OpenAI error: {error}"
MSG_ERROR_OPENAI_UNEXPECTED_LOG = "Unexpected OpenAI error: {}"
MSG_DEBUG_API_EXCEPTION = "Full exception details:"
MSG_DEBUG_PARSED_STRUCTURED_DATA = "Parsed structured data: %s"
MSG_ERROR_LLM_JSON_DECODE_LOG = "Failed to decode JSON from LLM response: %r [URL: %s]"


# fetcher.py
MSG_INFO_FETCH_SUCCESS = "Fetched {} successfully"
MSG_WARNING_FETCH_FAILED = "Failed to fetch %s: %s"
MSG_FETCH_ERROR_PREFIX = "__FETCH_ERROR__"

# models.py
MSG_ERROR_EMPTY_STRING = "Field '{field}' must not be empty or whitespace."
MSG_ERROR_INVALID_PRICE = "Price must be non-negative. Got: {value}"

# parser.py
MSG_DEBUG_PARSED_TITLE = "Parsed <title>: %s"
MSG_DEBUG_PARSED_META_DESCRIPTION = "Parsed meta description: %s"
MSG_DEBUG_PARSED_AUTHOR = "Parsed author from %s: %s"
MSG_INFO_NO_TITLE = "No <title> tag found."
MSG_INFO_NO_META_DESCRIPTION = "No meta description found."
MSG_INFO_NO_AUTHOR = "No author meta tag found."

# screenshotter.py
MSG_ERROR_SCREENSHOT_FAILED = "Failed to capture screenshot"
MSG_INFO_SCREENSHOT_SAVED = "Screenshot saved: %s"

# worker_pool.py
MSG_ERROR_WORKER_FAILED = "Worker failed for URL: %s"
MSG_WARNING_WORKER_FAILED_SHORT = "Worker failed for URL: %s: %s"


# ---------------------------------------------------------------------
# common/logging.py
# ---------------------------------------------------------------------

# streamlit_ui.py
MSG_INFO_UI_STARTED = "Streamlit UI started."
MSG_WARNING_NO_INPUT_URL = "No input URL provided."
MSG_ERROR_EXTRACTION_ABORTED = "Extraction aborted due to previous errors."

# ---------------------------------------------------------------------
# config/
# ---------------------------------------------------------------------


# ---------------------------------------------------------------------
# common/logging.py
# ---------------------------------------------------------------------

MSG_INFO_LOGGING_INITIALIZED = "Logging initialized. Logs will be written to {path}"
MSG_WARNING_LOG_FILE_FAIL = "Failed to write log file to: {path}"

# ---------------------------------------------------------------------
# utils/
# ---------------------------------------------------------------------

# validators.py
MSG_DEBUG_SKIPPED_INVALID_URL = "Skipping invalid URL input: {url!r}"
MSG_ERROR_NOT_A_DIRECTORY = "Path %s exists but is not a directory."
