# frontend/app.py

MSG_INFO_FETCHING_URLS = "Fetching and processing %d URLs"
MSG_INFO_EXTRACTION_COMPLETE = "Completed extraction for %d URLs"

# ---------------------------------------------------------------------
# core/
# ---------------------------------------------------------------------
# settings.py
# core/settings.py

MSG_DEBUG_SETTINGS_LOADED = "Loaded settings: %s"
MSG_ERROR_MISSING_API_KEY = "OPENAI_API_KEY is required in your .env file."

MSG_DEBUG_USING_MODEL = "Using model: %s"
MSG_DEBUG_MAX_TOKENS = "Max tokens: %d"
MSG_DEBUG_TEMPERATURE = "Temperature: %.2f"
MSG_DEBUG_API_KEY_PREFIX = "OpenAI key loaded with prefix: %s"
MSG_DEBUG_PROJECT_ID = "Using project ID: %s"

MSG_DEBUG_ENVIRONMENT = "Environment: %s"
MSG_DEBUG_DEBUG_MODE = "Debug mode: %s"
MSG_DEBUG_CONCURRENCY = "Concurrency: %d"


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

MSG_ERROR_MISSING_LLM_CONTENT = "No valid message content returned from OpenAI."
MSG_ERROR_LLM_RESPONSE_MALFORMED = "LLM response missing or malformed: %s (%s)"
MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT = "LLM response message was present but content was None."
MSG_ERROR_JSON_DECODING_FAILED = "Failed to parse structured output from LLM: {error}"
MSG_ERROR_LLM_JSON_DECODE_LOG = "Failed to decode JSON from LLM response: %s (%s)"

MSG_ERROR_RATE_LIMIT = (
    "OpenAI quota exceeded. Please check your usage and billing at "
    "https://platform.openai.com/account/usage."
)
MSG_ERROR_RATE_LIMIT_LOG = "OpenAI quota exceeded: %s"

MSG_ERROR_API = "OpenAI API error occurred: {error}"
MSG_ERROR_API_LOG = "OpenAI API error occurred: %s"
MSG_DEBUG_API_EXCEPTION = "Full exception details:"

MSG_ERROR_OPENAI_UNEXPECTED = "Unexpected OpenAI error: {error}"
MSG_ERROR_OPENAI_UNEXPECTED_LOG = "Unexpected OpenAI error: %s"

# fetcher.py

MSG_INFO_FETCH_SUCCESS = "Fetched %s successfully"
MSG_WARNING_FETCH_FAILED = "Failed to fetch %s: %s"
MSG_FETCH_ERROR_PREFIX = "__FETCH_ERROR__"

# parser.py
MSG_DEBUG_PARSED_TITLE = "Parsed <title>: %s"
MSG_DEBUG_PARSED_META_DESCRIPTION = "Parsed meta description: %s"
MSG_DEBUG_PARSED_AUTHOR = "Parsed author from %s: %s"
MSG_INFO_NO_TITLE = "No <title> tag found."
MSG_INFO_NO_META_DESCRIPTION = "No meta description found."
MSG_INFO_NO_AUTHOR = "No author meta tag found."


# screenshotter.py
MSG_ERROR_SCREENSHOT_FAILED = "Failed to capture screenshot for %s"
MSG_INFO_SCREENSHOT_SAVED = "Screenshot saved: %s"


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
