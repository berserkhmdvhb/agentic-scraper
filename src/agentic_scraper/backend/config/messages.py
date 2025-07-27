# ─── Frontend ───

# frontend/app.py
MSG_INFO_FETCHING_URLS = "Fetching and processing {n} URLs"
MSG_INFO_EXTRACTION_COMPLETE = "Completed extraction for {n} URLs"
MSG_WARNING_EXTRACTION_NONE = "Pipeline ended without extracting any items"
MSG_INFO_FETCH_SKIPPED = "Skipped {n} URLs due to fetch errors"
MSG_ERROR_PROCESSING_URL_FAILED = "Error processing {url}: {exc}"
MSG_WARN_PROCESSING_URL_FAILED = "⚠️ Failed to process {url}: {error}"

MSG_INFO_INVALID_URLS_SKIPPED = "⚠️ {n} line(s) were skipped due to invalid URL formatting."
MSG_INFO_NO_VALID_URLS = "⚠️ No valid URLs found."
MSG_INFO_USING_CACHE = "🔁 Using cached results for these URLs."
MSG_INFO_VALID_URLS_FOUND = "✅ {n} valid URLs detected."
MSG_SUCCESS_EXTRACTION_DONE = "✅ Extraction done!"
MSG_ERROR_EXTRACTION_FAILED = "❌ LLM extraction failed: {error}"
MSG_EXCEPTION_UNEXPECTED_PIPELINE_ERROR = "Unexpected error during extraction pipeline"
MSG_INFO_APP_RESET_TRIGGERED = "User triggered app reset via sidebar."

# ─── Backend ───

# ---------------------------------------------------------------------
# api/
# ---------------------------------------------------------------------

# main.py
MSG_INFO_SCRAPE_REQUEST_RECEIVED = "Received scrape request for {n} URL(s)"

# lifecycle.py
MSG_INFO_SHUTDOWN_LOG = "Shutdown complete, cleaning up resources..."
MSG_INFO_PRELOADING_JWKS = "Preloading JWKS from Auth0..."
MSG_DEBUG_LIFESPAN_STARTED = "Lifespan started for app: {app}"
MSG_INFO_JWKS_PRELOAD_SUCCESSFUL = "JWKS preload successful. The app is ready to handle requests."



# user_store.py
MSG_ERROR_INVALID_CREDENTIALS = "Error saving credentials for user {user_id}: {error}"
MSG_ERROR_DECRYPTION_FAILED = "Error decrypting credentials for user {user_id}: {error}"
MSG_ERROR_LOADING_USER_STORE = "Failed to load user store"
MSG_ERROR_SAVING_USER_STORE = "Failed to save user store: {error}"
MSG_WARNING_CREDENTIALS_NOT_FOUND = "Credentials not found for user {user_id}"

# auth/dependencies.py
# ruff: noqa: S105
MSG_ERROR_INVALID_TOKEN = "Invalid or expired token: {error}"
MSG_WARNING_INSUFFICIENT_PERMISSIONS = "User does not have required permissions: {scopes}"
MSG_ERROR_INTERNAL_SERVER = "Internal server error during token validation: {error}"
MSG_ERROR_MISSING_SCOPES = "The token is missing one or more required scopes: {scopes}"


# auth/auth0_helpers.py

MSG_INFO_FETCHING_JWKS = "Fetching JWKS from {url}..."
MSG_INFO_JWKS_FETCHED = "{num_keys} keys fetched from JWKS."
MSG_INFO_DECODING_JWT = "Decoding JWT..."
MSG_ERROR_FETCHING_JWKS = "Error fetching JWKS: {error}"
MSG_ERROR_INVALID_JWT_HEADER = "Invalid JWT header"
MSG_ERROR_NO_RSA_KEY = "No RSA key found matching the JWT header's 'kid': {kid}"
MSG_ERROR_JWT_EXPIRED = "JWT has expired: {error}"
MSG_ERROR_JWT_VERIFICATION = "JWT verification failed: {error}"
MSG_ERROR_JWT_UNEXPECTED = "Unexpected error while processing JWT: {error}"
MSG_INFO_RETRYING = "Retrying... (Attempt {attempt}/{retry_limit})"

# auth/scope_helpers.py
MSG_DEBUG_MISSING_SCOPES = (
    "User is missing the following required scopes: {missing_scopes}. "
    "User's current scopes: {user_scopes}."
)
MSG_DEBUG_CURRENT_ISSUER = "Current issuer is: {issuer}"
MSG_INFO_DECODED_TOKEN = "Decoded token: {decoded_token}"

# auth/log_helpers.py
MSG_WARNING_USER_FAILED_AUTHORIZATION = "User {user_id} failed to authorize."

# routes/user.py
MSG_WARNING_NO_CREDENTIALS_FOUND = "No OpenAI credentials found for user {user_id}"


# ---------------------------------------------------------------------
# core/
# ---------------------------------------------------------------------

# settings.py
MSG_DEBUG_SETTINGS_LOADED = "Settings loaded successfully:"
MSG_DEBUG_SETTINGS_LOADED_WITH_VALUES = "Settings loaded successfully:\n{values}"
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
MSG_ERROR_BACKOFF_MIN_GREATER_THAN_MAX = (
    "Retry backoff min ({min}) cannot be greater than max ({max})."
)
MSG_ERROR_LOG_BACKUP_COUNT_INVALID = "Log backup count must be > 0 if log_max_bytes > 0."


# settings_helpers.py
MSG_DEBUG_SETTING_OVERRIDDEN = "Overridden {key} = {validated!r} (from env: {original!r})"
MSG_DEBUG_SETTING_SKIPPED = "Skipping {key}: blank or unset → using default"
MSG_WARNING_SETTING_INVALID = "Invalid {key}={original!r}: {error}"


# ---------------------------------------------------------------------
# scraper/
# ---------------------------------------------------------------------

# fetcher.py
MSG_INFO_FETCH_SUCCESS = "Fetched {url} successfully"
MSG_WARNING_FETCH_FAILED = "Failed to fetch {url}"
MSG_ERROR_UNREACHABLE_FETCH_URL = "Unreachable code reached in fetch_url (unexpected fallback)"
MSG_DEBUG_RETRYING_URL = "Retrying {url} (attempt {no}): previous failure was {exc!r}"
MSG_ERROR_UNEXPECTED_FETCH_EXCEPTION = "Unexpected exception while fetching {url}"


# models.py
MSG_ERROR_EMPTY_STRING = "Field '{field}' must not be empty or whitespace."
MSG_ERROR_INVALID_PRICE = "Price must be non-negative. Got: {value}"

# parser.py
MSG_DEBUG_PARSED_TITLE = "Parsed <title>: {title}"
MSG_DEBUG_PARSED_META_DESCRIPTION = "Parsed meta description: {description}"
MSG_DEBUG_PARSED_AUTHOR = "Parsed author from {source}: {author}"
MSG_INFO_NO_TITLE = "No <title> tag found."
MSG_INFO_NO_META_DESCRIPTION = "No meta description found."
MSG_INFO_NO_AUTHOR = "No author meta tag found."

# screenshotter.py
MSG_ERROR_SCREENSHOT_FAILED = "Failed to capture screenshot"
MSG_INFO_SCREENSHOT_SAVED = "Screenshot saved: {path}"
MSG_INFO_WORKER_POOL_START = "Running worker pool with screenshots enabled = {enabled}"


# worker_pool.py
MSG_ERROR_WORKER_FAILED = "Worker failed for URL: {url}"
MSG_WARNING_WORKER_FAILED_SHORT = "Worker failed for URL: {url}: {error}"
MSG_DEBUG_WORKER_PROGRESS = (
    "[Worker-{worker_id}] Processed: {url} | Remaining in queue: {remaining}"
)


# ---------------------------------------------------------------------
# scraper/agent/
# ---------------------------------------------------------------------

# agent_helpers.py
MSG_DEBUG_LLM_JSON_DUMP_SAVED = "Full LLM JSON output saved to {path}"
MSG_ERROR_SCREENSHOT_FAILED_WITH_URL = "Failed to capture screenshot. [URL: {url}]"
MSG_ERROR_RATE_LIMIT_LOG_WITH_URL = "OpenAI rate limit exceeded. [URL: {url}]"
MSG_ERROR_RATE_LIMIT_DETAIL = "Rate limit detail: {error}"
MSG_ERROR_OPENAI_UNEXPECTED_LOG_WITH_URL = "Unexpected OpenAI error. [URL: {url}]"
MSG_ERROR_OPENAI_UNEXPECTED = "Unexpected OpenAI error: {error}"
MSG_ERROR_OPENAI_UNEXPECTED_LOG = "Unexpected OpenAI error: {exc}"
MSG_ERROR_LLM_JSON_DECODE_LOG = "Failed to decode JSON from LLM response: {exc!r} [URL: {url}]"
MSG_ERROR_JSON_DECODING_FAILED_WITH_URL = "Failed to parse LLM output: {exc} [URL: {url}]"
MSG_ERROR_API_LOG_WITH_URL = "OpenAI API error occurred. [URL: {url}]"
MSG_ERROR_API = "OpenAI API error occurred: {error}"
MSG_DEBUG_PARSED_STRUCTURED_DATA = "Parsed structured data: {data}"
MSG_DEBUG_API_EXCEPTION = "Full exception details:"


# llm_fixed.py
MSG_SYSTEM_PROMPT = """You are a web extraction assistant.
Your job is to extract key data from webpage content.
Return only a JSON object with the following fields:
- title (string or null)
- description (string or null)
- price (float or null)
- author (string or null)
- date_published (string or null)

All values must be valid JSON. If a field is not found, return null for it."""
MSG_ERROR_LLM_RESPONSE_MALFORMED_WITH_URL = "LLM response missing or malformed. [URL: {url}]"
MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL = "LLM response was None. [URL: {url}]"

MSG_ERROR_RATE_LIMIT = (
    "OpenAI quota exceeded. Please check your usage and billing at "
    "https://platform.openai.com/account/usage."
)
MSG_ERROR_RATE_LIMIT_LOG = "OpenAI quota exceeded."

MSG_ERROR_API_LOG = "OpenAI API error occurred: {exc}"

MSG_INFO_EXTRACTION_SUCCESS_WITH_URL = "Extracted structured data from: {url}"
MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL = "Failed to validate LLM response for {url}: {exc}"

# __init__.py
MSG_ERROR_INVALID_AGENT_MODE = "Invalid agent mode: '{value}'. Valid options: {valid_options}"
MSG_ERROR_UNHANDLED_AGENT_MODE = "Unhandled AGENT_MODE: {value}"


# rule_based.py
MSG_DEBUG_RULE_BASED_EXTRACTION_FAILED = (
    "Rule-based extraction failed to construct ScrapedItem for {url}: {error}"
)

# llm_dynamic_adaptive.py

MSG_DEBUG_MISSING_IMPORTANT_FIELDS = (
    "Missing critical fields {fields} in first pass, retrying with recovery prompt..."
)

MSG_INFO_ADAPTIVE_EXTRACTION_SUCCESS_WITH_URL = (
    "Adaptive LLM extraction succeeded for {url} with field recovery if needed."
)

MSG_DEBUG_CONTEXTUAL_HINTS_USED = (
    "Using context hints for {url}: meta={meta},"
    " breadcrumbs={breadcrumbs}, url_segments={url_segments}"
)
MSG_WARN_ADAPTIVE_EXTRACTION_FAILED_AFTER_RETRIES = (
    "Failed to extract sufficient fields after {attempts} adaptive attempts for {url}"
)
MSG_DEBUG_USING_BEST_CANDIDATE_FIELDS = "Using best candidate with fields: {fields}"
MSG_DEBUG_LLM_RETRY_ATTEMPT = "LLM retry attempt {attempt}/{total} for {url}"
MSG_WARN_LLM_RATE_LIMIT_SLEEP = "Rate limit hit for {url}, sleeping {delay:.1f}s as advised..."
MSG_DEBUG_FIELD_SCORE_PER_RETRY = "[{url}] Retry #{attempt}: score={score}, fields={fields}"

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
MSG_ERROR_NOT_A_DIRECTORY = "Path {path} exists but is not a directory."
MSG_ERROR_UNSUPPORTED_OPENAI_MODEL = (
    "Unsupported OpenAI model: {model!r}. Must be one of: {valid_models}"
)
MSG_ERROR_BACKOFF_MIN_NEGATIVE = "Retry backoff min must be non-negative."
MSG_ERROR_BACKOFF_MAX_NEGATIVE = "Retry backoff max must be non-negative."
MSG_ERROR_BACKOFF_MIN_GT_MAX = "Retry backoff min must be less than or equal to max."
MSG_ERROR_RETRY_NEGATIVE = "Retry attempts must be non-negative"
MSG_ERROR_INVALID_PRICE_FORMAT = "Invalid price format: {value}"

MSG_ERROR_INVALID_AUTH0_DOMAIN = (
    "AUTH0_DOMAIN must be a valid Auth0 domain (e.g., dev-xxx.us.auth0.com)"
)
MSG_ERROR_INVALID_API_AUDIENCE = "API_AUDIENCE must be a valid URL (e.g., https://api.example.com/)"
MSG_ERROR_INVALID_ENCRYPTION_SECRET = "ENCRYPTION_SECRET must be at least {value} characters long"
MSG_ERROR_INVALID_AUTH0_ALGORITHMS = "Invalid auth0_algorithms {algo}. Optionas are {valid_options}"
MSG_ERROR_EMPTY_AUTH0_ALGORITHMS = "auth0_algorithms must not be empty"
MSG_ERROR_UNEXPECTED_EXCEPTION = "Unexpected error during token validation."
MSG_INFO_USER_AUTHORIZED = "User successfully authenticated and authorized."
MSG_ERROR_USER_SCOPES_TYPE = (
    "Expected 'user_scopes' to be a list of strings, "
    "got {type(user_scopes)}"
)


MSG_ERROR_PRELOADING_JWKS = "Error occurred while preloading JWKS from Auth0: {error}"
