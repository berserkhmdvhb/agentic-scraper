# ─── Frontend ───

# app.py
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

MSG_UI_RESET_COMPLETE = "Reset complete. Defaults restored."

# ui_auth.py
MSG_INFO_JWT_STORED = "[FRONTEND] [AUTH] JWT token stored in session. Length: {length}"
MSG_INFO_NO_JWT_FOUND = "[FRONTEND] [AUTH] No JWT token found; user not logged in yet."
MSG_WARNING_MALFORMED_JWT = "[FRONTEND] [AUTH] Suspected malformed JWT (segments = {segments})"
MSG_WARNING_NO_TOKEN_FOUND = "[FRONTEND] [AUTH] No token found in URL or session"

MSG_ERROR_FETCH_USER_PROFILE = "[FRONTEND] [AUTH] Failed to fetch user profile: {error}"
MSG_ERROR_NETWORK_USER_PROFILE = (
    "[FRONTEND] [AUTH] Network error while fetching user profile: {error}"
)
MSG_ERROR_NETWORK_CREDENTIALS = (
    "[FRONTEND] [AUTH] Network error while fetching credentials: {error}"
)

MSG_INFO_PROFILE_FETCHED = "[FRONTEND] [AUTH] User profile fetched successfully"
MSG_INFO_CREDENTIALS_FETCHED = "[FRONTEND] [AUTH] OpenAI credentials fetched and stored"

MSG_DEBUG_JWT_FROM_URL = "[FRONTEND] [AUTH] Extracted token from URL: {token}"
MSG_WARNING_MALFORMED_JWT = "[FRONTEND] [AUTH] Suspected malformed JWT: {token}"
MSG_WARNING_NO_JWT_FOUND = "[FRONTEND] [AUTH] No token found in URL or session"
MSG_EXCEPTION_USER_PROFILE = "[FRONTEND] [AUTH] Failed to fetch user profile: {error}"
MSG_EXCEPTION_USER_PROFILE_NETWORK = "[FRONTEND] [AUTH] Network error while fetching user profile"
MSG_INFO_USER_PROFILE_SUCCESS = "[FRONTEND] [AUTH] User profile fetched successfully"
MSG_INFO_CREDENTIALS_SUCCESS = "[FRONTEND] [AUTH] OpenAI credentials fetched and stored"
MSG_EXCEPTION_OPENAI_CREDENTIALS = "Failed to fetch OpenAI credentials: {error}"
MSG_EXCEPTION_OPENAI_CREDENTIALS_NETWORK = (
    "[FRONTEND] [AUTH] Network error while fetching OpenAI credentials"
)
MSG_INFO_TOKEN_SESSION_LENGTH = "[FRONTEND] [AUTH] JWT token stored in session. Length: {length}"
MSG_INFO_NO_TOKEN_YET = "[FRONTEND] [AUTH] No JWT token found; user not logged in yet."
MSG_INFO_AUTH0_LOGIN_URI = "[FRONTEND] [AUTH] Auth0 login URI: {uri}"

MSG_UI_LOGGED_OUT_APP_ONLY = "You've logged out of this app."
MSG_UI_LOGGING_IN = "Logging you in…"

# ui_auth_helpers.py
MSG_LOG_TOKEN_FROM_SESSION_STATE = "[FRONTEND] [AUTH] Token from session state (not URL)"
MSG_INFO_AUTH0_LOGIN_URI = "[FRONTEND] [AUTH] Auth0 login URL computed: {uri}"
MSG_INFO_AUTH0_FORCE_LOGIN_URI = "[FRONTEND] [AUTH] Auth0 force-login URL computed: {uri}"
MSG_INFO_AUTH0_LOGOUT_URI = "[FRONTEND] [AUTH] Auth0 logout URL computed: {uri}"


# ui_runner.py

UI_SCRAPE_PREFIX = "[FRONTEND] [PIPELINE] "
MSG_ERROR_USER_NOT_AUTHENTICATED = "User is not authenticated!"
MSG_ERROR_CREATE_JOB = "Failed to create job: {error}"
MSG_WARNING_JOB_NOT_FOUND = "Job not found (404)."
MSG_ERROR_FORBIDDEN_JOB_ACCESS = "Forbidden: you do not own this job."
MSG_INFO_JOB_NOT_CANCELABLE = "Job is not cancelable (already finished)."
MSG_ERROR_CANCEL_FAILED = "Cancel failed: {error}"
MSG_ERROR_NETWORK_HTTP = "Network/HTTP error: {error}"
MSG_INFO_CREATING_JOB_SPINNER = "🔍 Creating job..."
MSG_INFO_RUNNING_JOB_SPINNER = "⏳ Running scrape job..."
MSG_ERROR_BACKEND_NO_JOB_ID = "Backend did not return a job id."
MSG_ERROR_MISSING_OPENAI_CREDENTIALS = (
    "Missing OpenAI credentials. "
    "Please provide your API key and project ID before running LLM-based scraping."
)
MSG_ERROR_INVALID_AGENT_MODE = "Invalid agent mode: {mode}"
MSG_ERROR_MISSING_LLM_FIELDS = "Missing LLM fields before send: {fields}"
MSG_ERROR_POLLING_TIMEOUT = "Polling timed out."

MSG_DEBUG_SCRAPE_CONFIG_MERGED = UI_SCRAPE_PREFIX + "config values before calling API: {config}"
MSG_DEBUG_REQUEST_TARGET = UI_SCRAPE_PREFIX + "Requesting {method} {url}"
MSG_DEBUG_REQUEST_PAYLOAD_KEYS = (
    UI_SCRAPE_PREFIX + "Payload keys: {keys} (agent_mode={mode} type={type})"
)
MSG_DEBUG_LLM_FIELDS_ATTACHED = UI_SCRAPE_PREFIX + "LLM fields attached: {fields}"
MSG_WARNING_LLM_FIELDS_MISSING = UI_SCRAPE_PREFIX + "Missing required LLM fields: {fields}"
MSG_DEBUG_RESPONSE_META = UI_SCRAPE_PREFIX + "Response status={status} location={location}"
MSG_DEBUG_RESPONSE_BODY_COMPACT = UI_SCRAPE_PREFIX + "Response body (truncated): {body}"
MSG_DEBUG_JOB_ID_FROM_BODY = UI_SCRAPE_PREFIX + "Using job id from body: {job_id}"
MSG_DEBUG_JOB_ID_FROM_LOCATION = UI_SCRAPE_PREFIX + "Using job id from Location: {job_id}"
MSG_ERROR_HTTP_COMPACT = UI_SCRAPE_PREFIX + "HTTP error {method} {url}: {error}"
MSG_DEBUG_POLL_START = (
    UI_SCRAPE_PREFIX + "Poll start job={job_id} interval={interval}s timeout={timeout}s"
)
MSG_DEBUG_POLL_STATUS_CHANGE = (
    UI_SCRAPE_PREFIX + "Job {job_id} status→{status} progress={progress} items={items}"
)
MSG_INFO_POLL_DONE_SUCCEEDED = (
    UI_SCRAPE_PREFIX + "Job {job_id} SUCCEEDED items={items} skipped={skipped}"
)
MSG_WARNING_POLL_DONE_FAILED = UI_SCRAPE_PREFIX + "Job {job_id} {status} error={error}"
MSG_WARNING_POLL_TIMEOUT = UI_SCRAPE_PREFIX + "Poll timeout job={job_id} after {elapsed}s"
MSG_DEBUG_PIPELINE_INPUT = UI_SCRAPE_PREFIX + "URLs: valid={valid} invalid={invalid}"
MSG_DEBUG_CACHE_DECISION = UI_SCRAPE_PREFIX + "Cache {decision} key={key}"
MSG_ERROR_MISSING_JWT = UI_SCRAPE_PREFIX + "Missing JWT in session state"

# ui_runner_helpers.py
MSG_DEBUG_PARSE_RESULT_SUMMARY = (
    UI_SCRAPE_PREFIX + "Parse: raw_items={raw} "
    "valid={valid} "
    "malformed={malformed} "
    "num_failed={num_failed} "
    "duration={duration}s"
)
MSG_WARNING_PARSE_ITEM_SKIPPED = UI_SCRAPE_PREFIX + "Skipped malformed result #{idx}: {error}"

MSG_DEBUG_INLINE_KEY_MASKED_OMIT = (
    "[FRONTEND] [RUNNER] Inline OpenAI key appearsmasked/placeholder; omitting to use stored creds."
)
# ui_jobs.py
MSG_ERROR_BACKEND_DOMAIN_NOT_CONFIGURED = "Backend domain is not configured."
MSG_ERROR_LIST_JOBS = "Failed to list jobs: {error}"
MSG_ERROR_LIST_JOBS_NETWORK = "Network error while listing jobs: {error}"
MSG_ERROR_FETCH_JOB = "Failed to fetch job: {error}"
MSG_ERROR_FETCH_JOB_NETWORK = "Network error while fetching job: {error}"
MSG_WARNING_JOB_NOT_FOUND = "Job not found (404)."
MSG_ERROR_FORBIDDEN_JOB_ACCESS = "Forbidden: you do not own this job."
MSG_SUCCESS_JOB_CANCELED = "Job canceled."
MSG_INFO_JOB_NOT_CANCELABLE = "Job is not cancelable (already finished)."
MSG_ERROR_CANCEL_JOB = "Failed to cancel job: {error}"
MSG_ERROR_CANCEL_JOB_NETWORK = "Network error while canceling job: {error}"
MSG_INFO_NO_JOBS_FOUND = "No jobs found."
MSG_INFO_LOGIN_TO_VIEW_JOBS = "🔐 Please log in to view your jobs."
MSG_INFO_NO_RESULTS = "📭 No results found for this job."


MSG_INFO_NO_RESULTS = "⚠️ No data could be extracted."
MSG_INFO_JOB_CANCELED = "🛑 Job was canceled."
MSG_ERROR_JOB_FAILED = "Job failed."


# ─── Backend ───

# ---------------------------------------------------------------------
# api/
# ---------------------------------------------------------------------

# main.py
MSG_INFO_SCRAPE_REQUEST_RECEIVED = "[API] Received scrape request for {n} URL(s)"


# lifecycle.py
MSG_INFO_SHUTDOWN_LOG = "[API] [LIFECYCLE] Shutdown complete, cleaning up resources..."
MSG_INFO_PRELOADING_JWKS = "[API] [LIFECYCLE] Preloading JWKS from Auth0..."
MSG_DEBUG_LIFESPAN_STARTED = "[API] [LIFECYCLE] Lifespan started for app: {app}"
MSG_INFO_JWKS_PRELOAD_SUCCESSFUL = (
    "[API] [LIFECYCLE] JWKS preload successful. The app is ready to handle requests."
)
MSG_WARNING_JWKS_PRELOAD_FAILED_STARTING_LAZILY = (
    "[API] [LIFECYCLE] JWKS preload failed;continuing startup and fetching JWKS lazily."
)

# models.py
MSG_ERROR_OWNER_SUB_TYPE = "[API] owner_sub must be a string"
MSG_ERROR_OWNER_SUB_FORMAT = "[API] Invalid owner_sub format: {value!r}"


# user_store.py
MSG_ERROR_INVALID_CREDENTIALS = (
    "[API] [USERSTORE] Error saving credentials for user {user_id}: {error}"
)
MSG_ERROR_DECRYPTION_FAILED = (
    "[API] [USERSTORE] Error decrypting credentials for user {user_id}: {error}"
)
MSG_ERROR_LOADING_USER_STORE = "[API] [USERSTORE] Failed to load user store"
MSG_ERROR_SAVING_USER_STORE = "[API] [USERSTORE] Failed to save user store: {error}"
MSG_WARNING_CREDENTIALS_NOT_FOUND = "[API] [USERSTORE] Credentials not found for user {user_id}"
MSG_INFO_CREDENTIALS_DELETED = "[API] [USERSTORE] Deleted credentials for user: {user_id}"


# auth/dependencies.py
# ruff: noqa: S105
MSG_ERROR_INVALID_TOKEN = "[API] [AUTH] [DEP] Invalid or expired token: {error}"
MSG_WARNING_INSUFFICIENT_PERMISSIONS = (
    "[API] [AUTH] [DEP] User does not have required permissions: {scopes}"
)
MSG_ERROR_INTERNAL_SERVER = (
    "[API] [AUTH] [DEP] Internal server error during token validation: {error}"
)
MSG_ERROR_MISSING_SCOPES = (
    "[API] [AUTH] [DEP] The token is missing one or more required scopes: {scopes}"
)
MSG_DEBUG_VERIFYING_JWT_TOKEN = "[API] [AUTH] [DEP] Verifying JWT token: {token}"
MSG_WARNING_JWT_VERIFICATION_FAILED = "[API] [AUTH] [DEP] JWT verification failed"
MSG_ERROR_MISSING_SUB_CLAIM = "[API] [AUTH] [DEP] Missing 'sub' in token payload"

# auth/auth0_helpers.py
MSG_INFO_FETCHING_JWKS = "[API] [AUTH] [AUTH0] Fetching JWKS from {url}..."
MSG_INFO_JWKS_FETCHED = "[API] [AUTH] [AUTH0] {num_keys} keys fetched from JWKS."
MSG_INFO_DECODING_JWT = "[API] [AUTH] [AUTH0] Decoding JWT..."

MSG_ERROR_FETCHING_JWKS = "[API] [AUTH] [AUTH0] Error fetching JWKS: {error}"
MSG_ERROR_INVALID_JWT_HEADER = "[API] [AUTH] [AUTH0] Invalid JWT header"
MSG_ERROR_NO_RSA_KEY = (
    "[API] [AUTH] [AUTH0] No RSA key found matching the JWT header's 'kid': {kid}"
)
MSG_ERROR_JWT_EXPIRED = "[API] [AUTH] [AUTH0] JWT has expired: {error}"
MSG_ERROR_JWT_VERIFICATION = "[API] [AUTH] [AUTH0] JWT verification failed: {error}"
MSG_ERROR_JWT_UNEXPECTED = "[API] [AUTH] [AUTH0] Unexpected error while processing JWT: {error}"

MSG_INFO_RETRYING = "[API] [AUTH] [AUTH0] Retrying... (Attempt {attempt}/{retry_limit})"

# auth/scope_helpers.py
MSG_DEBUG_MISSING_SCOPES = (
    "[API] [AUTH] [AUTH0] User is missing the following required scopes: {missing_scopes}. "
    "User's current scopes: {user_scopes}."
)
MSG_DEBUG_CURRENT_ISSUER = "[API] [AUTH] [AUTH0] Current issuer is: {issuer}"
MSG_INFO_DECODED_TOKEN = "[API] [AUTH] [AUTH0] Decoded token: {decoded_token}"

# auth/log_helpers.py
MSG_WARNING_USER_FAILED_AUTHORIZATION = "[API] [AUTH] [AUTH0] User {user_id} failed to authorize."

# routes/auth.py
MSG_WARNING_AUTH_CALLBACK_MISSING_CODE = "[API] [ROUTE] [AUTH] Missing 'code' in query params"
MSG_DEBUG_AUTH_CALLBACK_CODE_RECEIVED = (
    "[API] [ROUTE] [AUTH] Auth0 code received in callback: {code}"
)
MSG_ERROR_AUTH_TOKEN_EXCHANGE_FAILED = (
    "[API] [ROUTE] [AUTH] Auth0 token exchange failed. Status: {status}, Body: {body}"
)
MSG_ERROR_AUTH_RESPONSE_MISSING_TOKEN = "[API] [ROUTE] [AUTH] Auth0 response missing access_token"
MSG_DEBUG_AUTH_TOKEN_RECEIVED = (
    "[API] [ROUTE] [AUTH] Access token received: {token_preview}... [truncated]"
)
MSG_DEBUG_AUTH_REDIRECT_URL = (
    "[API] [ROUTE] [AUTH] Redirecting to frontend with token in URL: {redirect_url}"
)
MSG_EXCEPTION_AUTH_CALLBACK_FAILURE = (
    "[API] [ROUTE] [AUTH] Token exchange failed during Auth0 callback"
)
MSG_INFO_AUTH_CALLBACK_DURATION = "[API] [ROUTE] [AUTH] Auth0 callback completed in {duration:.2f}s"

# routes/user.py
MSG_WARNING_NO_CREDENTIALS_FOUND = (
    "[API] [ROUTE] [USER] No OpenAI credentials found for user {user_id}"
)
MSG_INFO_CREDENTIALS_SAVED = "[API] [ROUTE] [USER] OpenAI credentials saved for user: {user_id}"
MSG_INFO_CREDENTIALS_LOADED = "[API] [ROUTE] [USER] OpenAI credentials loaded for user: {user_id}"

MSG_ERROR_NO_CREDENTIALS_FOR_USER = "[API] [ROUTE] [USER] No credentials stored for this user."
MSG_ERROR_PARSING_CREDENTIALS = "[API] [ROUTE] [USER] Error while parsing credentials data."
MSG_ERROR_UNEXPECTED_CREDENTIALS = (
    "[API] [ROUTE] [USER] Unexpected errorwhile processing credentials."
)
MSG_ERROR_INVALID_CREDENTIALS_FORMAT = "Invalid data format for credentials."
MSG_ERROR_CREDENTIALS_STORAGE = "[API] [ROUTE] [USER] Error with the database or file storage."
MSG_ERROR_CREDENTIALS_SAVE_INTERNAL = (
    "[API] [ROUTE] [USER] Failed tosave user credentials due to internal error."
)
MSG_ERROR_NO_CREDENTIALS_TO_DELETE = "[API] [ROUTE] [USER] No credentials found to delete."
MSG_ERROR_CREDENTIALS_DELETE_FAILED = "[API] [ROUTE] [USER] Failed to delete credentials."


# routes/scrape.py
MSG_DEBUG_SCRAPE_CONFIG_MERGED = (
    "[API] [ROUTE] [SCRAPE] Backend config values merged with settings: {config}"
)
MSG_ERROR_MISSING_FIELDS_FOR_AGENT = (
    "[API] [ROUTE] [SCRAPE] Missing required "
    "fields for agent_mode '{agent_mode}': {missing_fields}."
)

MSG_JOB_CREATED = "[API] [ROUTE] [SCRAPE] job created: {job_id}"
MSG_JOB_STARTED = "[API] [ROUTE] [SCRAPE] job started: {job_id}"
MSG_JOB_PROGRESS = "[API] [ROUTE] [SCRAPE] job progress update: {job_id} {progress}"
MSG_JOB_SUCCEEDED = "[API] [ROUTE] [SCRAPE] job succeeded: {job_id}"
MSG_JOB_FAILED = "[API] [ROUTE] [SCRAPE] job failed: {job_id}"
MSG_JOB_NOT_FOUND = "[API] [ROUTE] [SCRAPE] job not found: {job_id}"
MSG_JOB_CANCELED = "[API] [ROUTE] [SCRAPE] job canceled: {job_id}"
MSG_ROUTE_DEPRECATED = "[API] [ROUTE] [SCRAPE] Deprecatedendpoint called: {route}. Use {successor}."
MSG_ERROR_INVALID_JOB_STATUS = "[API] [ROUTE] [SCRAPE] Invalid job status: {status}"

MSG_HTTP_JOB_NOT_FOUND_DETAIL = "[API] [ROUTE] [SCRAPE] Job not found."
MSG_HTTP_FORBIDDEN_JOB_ACCESS = (
    "[API] [ROUTE] [SCRAPE] User {user_sub} does not have permission to access job {job_id}."
)
MSG_HTTP_MISSING_OPENAI_CREDS = "OpenAI credentials not found for the authenticated user."

MSG_JOB_LIST_REQUESTED = (
    "[API] [ROUTE] [SCRAPE] List jobs requested: status={status}, limit={limit}, cursor={cursor}"
)
MSG_JOB_CANCEL_REQUESTED = "[API] [ROUTE] [SCRAPE] Cancel requested for job_id={job_id}"
MSG_JOB_CANCELED = "[API] [ROUTE] [SCRAPE] Job canceled: {job_id}"
MSG_HTTP_JOB_NOT_CANCELABLE = (
    "[API] [ROUTE] [SCRAPE] Job cannot be canceled in its current status: {status}."
)
MSG_JOB_CANCELED_BY_USER = "[API] [ROUTE] [SCRAPE] Job canceled: {job_id}, by user: {user_sub}"
MSG_HTTP_LOCATION_HEADER_SET = "[API] [ROUTE] [SCRAPE] Location header set for scrape job: {url}"
MSG_INFO_INLINE_KEY_MASKED_FALLBACK = (
    "[API] [ROUTE] [SCRAPE] Inline OpenAI key appears masked; falling back to stored credentials."
)


MSG_LOG_DEBUG_DYNAMIC_EXTRAS = (
    "DEBUG dynamic extras check | agent_mode={agent_mode} | first_item_keys={keys}"
)
MSG_LOG_DYNAMIC_EXTRAS_ERROR = "Failed to inspect first item for dynamic extras: {error}"

# ---------------------------------------------------------------------
# core/
# ---------------------------------------------------------------------

# settings.py
MSG_DEBUG_SETTINGS_LOADED = "[CONFIG] Settings loaded successfully:"
MSG_DEBUG_SETTINGS_LOADED_WITH_VALUES = "[CONFIG] Settings loaded successfully:\n{values}"
MSG_ERROR_MISSING_API_KEY = "[CONFIG] OPENAI_API_KEY is required in your .env file."
MSG_ERROR_INVALID_MODEL_NAME = (
    "[CONFIG] Invalid OpenAI model: {model}. Valid options: {valid_options}"
)
MSG_ERROR_INVALID_TEMPERATURE = "[CONFIG] Temperature must be between 0.0 and 2.0. Got: {value}"
MSG_ERROR_INVALID_TOKENS = "[CONFIG] Max tokens must be a positive integer. Got: {value}"
MSG_ERROR_INVALID_CONCURRENCY = "[CONFIG] Concurrency must be greater than 0. Got: {value}"
MSG_ERROR_INVALID_TIMEOUT = "[CONFIG] Request timeout must be greater than 0 seconds. Got: {value}"
MSG_ERROR_INVALID_LOG_LEVEL = "[CONFIG] Invalid log level: {value}. Valid options: {valid_options}"
MSG_ERROR_INVALID_LOG_BYTES = "[CONFIG] Log max bytes must be greater than 0. Got: {value}"
MSG_ERROR_INVALID_BACKUP_COUNT = "[CONFIG] Log backup count must be greater than 0. Got: {value}"
MSG_ERROR_INVALID_ENV = "[CONFIG] Invalid environment: {value}. Valid options: {valid_options}"
MSG_ERROR_BACKOFF_MIN_GREATER_THAN_MAX = (
    "[CONFIG] Retry backoff min ({min}) cannot be greater than max ({max})."
)
MSG_ERROR_LOG_BACKUP_COUNT_INVALID = "[CONFIG] Log backup count must be > 0 if log_max_bytes > 0."


# settings_helpers.py
MSG_DEBUG_SETTING_OVERRIDDEN = "[CONFIG] Overridden {key} = {validated!r} (from env: {original!r})"
MSG_DEBUG_SETTING_SKIPPED = "[CONFIG] Skipping {key}: blank or unset → using default"
MSG_WARNING_SETTING_INVALID = "[CONFIG] Invalid {key}={original!r}: {error}"


# ---------------------------------------------------------------------
# scraper/
# ---------------------------------------------------------------------

# fetcher.py
MSG_INFO_FETCH_SUCCESS = "[FETCHER] Fetched {url} successfully"
MSG_WARNING_FETCH_FAILED = "[FETCHER] Failed to fetch {url}"
MSG_ERROR_UNREACHABLE_FETCH_URL = (
    "[FETCHER] Unreachable code reached in fetch_url (unexpected fallback)"
)
MSG_DEBUG_RETRYING_URL = "[FETCHER] Retrying {url} (attempt {no}): previous failure was {exc!r}"
MSG_ERROR_UNEXPECTED_FETCH_EXCEPTION = "[FETCHER] Unexpected exception while fetching {url}"


# models.py
MSG_ERROR_EMPTY_STRING = "Field '{field}' must not be empty or whitespace."
MSG_ERROR_INVALID_PRICE = "Price must be non-negative. Got: {value}"

# parser.py
MSG_DEBUG_PARSED_TITLE = "[PARSER] Parsed <title>: {title}"
MSG_DEBUG_PARSED_META_DESCRIPTION = "[PARSER] Parsed meta description: {description}"
MSG_DEBUG_PARSED_AUTHOR = "[PARSER] Parsed author from {source}: {author}"
MSG_INFO_NO_TITLE = "[PARSER] No <title> tag found."
MSG_INFO_NO_META_DESCRIPTION = "[PARSER] No meta description found."
MSG_INFO_NO_AUTHOR = "[PARSER] No author meta tag found."

# screenshotter.py
MSG_ERROR_SCREENSHOT_FAILED = "[SCREENSHOT] Failed to capture screenshot"
MSG_INFO_SCREENSHOT_SAVED = "[SCREENSHOT] Screenshot saved: {path}"
MSG_INFO_WORKER_POOL_START = "[SCREENSHOT] Running worker pool with screenshots enabled = {enabled}"
MSG_ERROR_SCREENSHOT_FAILED = "[SCREENSHOT] Failed to capture screenshot"
MSG_INFO_SCREENSHOT_SAVED = "[SCREENSHOT] Screenshot saved to {path}"
MSG_ERROR_INVALID_SCREENSHOT_URL = "[SCREENSHOT] Invalid URL passed to capture_screenshot: {url}"


# worker_pool.py
WORKER_PREFIX = "[POOL] "
WORKER_ID_PREFIX = "[POOL] [WORKER {worker_id}] "

MSG_ERROR_WORKER_FAILED = WORKER_PREFIX + "failed for URL: {url}"
MSG_WARNING_WORKER_FAILED_SHORT = WORKER_PREFIX + "failed for URL: {url}: {error}"
MSG_DEBUG_WORKER_PROGRESS = WORKER_ID_PREFIX + "Processed: {url} | Remaining in queue: {remaining}"

MSG_DEBUG_WORKER_PICKED_URL = WORKER_ID_PREFIX + "Picked up URL: {url}"
MSG_DEBUG_WORKER_CREATED_REQUEST = WORKER_ID_PREFIX + "Created ScrapeRequest for {url}"
MSG_DEBUG_WORKER_GOT_ITEM = WORKER_ID_PREFIX + "extract_structured_data returned: {item}"
MSG_DEBUG_WORKER_ITEM_APPENDED = WORKER_ID_PREFIX + "Item appended for URL: {url}"
MSG_DEBUG_WORKER_NO_ITEM = WORKER_ID_PREFIX + "No item returned for URL: {url}"
MSG_DEBUG_WORKER_CANCELLED = WORKER_ID_PREFIX + "Cancelled during shutdown."

MSG_DEBUG_POOL_ENQUEUED_URL = WORKER_PREFIX + "Enqueued URL: {url}"
MSG_DEBUG_POOL_SPAWNED_WORKERS = WORKER_PREFIX + "Spawned {count} workers."
MSG_DEBUG_POOL_CANCELLING_WORKERS = WORKER_PREFIX + "All tasks completed. Cancelling workers..."
MSG_DEBUG_POOL_DONE = WORKER_PREFIX + "Worker pool finished. Total results: {count} in {time:.2f}s"

MSG_WARNING_TASK_DONE_FAILED = (
    WORKER_PREFIX + "failed to acknowledge task_done() for URL {url}: {error}"
)

MSG_WARNING_PROGRESS_COUNTER_FAILED = (
    WORKER_PREFIX + "failed updating processed counter for URL {url}: {error}"
)
MSG_WARNING_PROGRESS_LOG_FAILED = (
    WORKER_PREFIX + "failed during progress logging for URL {url}: {error}"
)
MSG_WARNING_PROGRESS_CALLBACK_FAILED = WORKER_PREFIX + "on_progress callback raised: {error}"
MSG_WARNING_PROGRESS_CALLBACK_FAILED_BUBBLE = (
    WORKER_PREFIX + "caught bubbled on_progress exception for URL {url}: {error}"
)
MSG_WARNING_ON_ITEM_CALLBACK_FAILED = (
    WORKER_PREFIX + "on_item_processed callback raised for URL {url}: {error}"
)

MSG_WARNING_ON_ITEM_PROCESSED_FAILED = WORKER_PREFIX + "on_item_processed callback failed: {error}"
MSG_WARNING_ON_ERROR_CALLBACK_FAILED = WORKER_PREFIX + "on_error callback failed: {error}"


# pipeline.py
MSG_DEBUG_SCRAPE_STATS_START = (
    "[PIPELINE] Starting scrape_with_stats: agent_mode={agent_mode}, "
    "openai_config_provided={has_openai}"
)

MSG_INFO_FETCH_COMPLETE = "[PIPELINE] Fetched HTML for {count} URLs"

MSG_INFO_VALID_SCRAPE_INPUTS = (
    "[PIPELINE] Prepared {valid} valid scrape inputs ({skipped} skipped due to fetch errors)"
)

MSG_INFO_SCRAPE_STATS_COMPLETE = (
    "[PIPELINE] Scraping completed: {total} total, "
    "{success} success, {failed} failed in {duration}s"
)

MSG_DEBUG_PIPELINE_WORKER_POOL_START = (
    "[PIPELINE] Launching worker pool with {count} inputs (LLM mode: {is_llm})"
)

MSG_DEBUG_PIPELINE_FETCH_START = "[PIPELINE] Starting HTML fetch for {count} URLs..."

# In backend/config/messages.py

MSG_DEBUG_JOB_HOOK_ON_STARTED_ERROR = "job_hooks.on_started raised an exception; ignoring."
MSG_DEBUG_JOB_HOOK_ON_COMPLETED_ERROR = "job_hooks.on_completed raised an exception; ignoring."
MSG_DEBUG_JOB_HOOK_ON_FAILED_ERROR = "job_hooks.on_failed raised an exception; ignoring."


# ---------------------------------------------------------------------
# scraper/agent/
# ---------------------------------------------------------------------

# --init--.py

MSG_DEBUG_AGENT_DISPATCH_START = (
    "[AGENT] Dispatching extract_structured_data ,with agent_mode={mode}"
)
MSG_DEBUG_AGENT_SELECTED = "[AGENT] Using {mode} extraction agent"


# agent_helpers.py
MSG_DEBUG_LLM_JSON_DUMP_SAVED = "[AGENT] Full LLM JSON output saved to {path}"
MSG_ERROR_SCREENSHOT_FAILED_WITH_URL = "[AGENT] Failed to capture screenshot. [URL: {url}]"
MSG_ERROR_RATE_LIMIT_LOG_WITH_URL = "[AGENT] OpenAI rate limit exceeded. [URL: {url}]"
MSG_ERROR_RATE_LIMIT_DETAIL = "[AGENT] Rate limit detail: {error}"
MSG_ERROR_OPENAI_UNEXPECTED_LOG_WITH_URL = "[AGENT] Unexpected OpenAI error. [URL: {url}]"
MSG_ERROR_OPENAI_UNEXPECTED = "[AGENT] Unexpected OpenAI error: {error}"
MSG_ERROR_OPENAI_UNEXPECTED_LOG = "[AGENT] Unexpected OpenAI error: {exc}"
MSG_ERROR_LLM_JSON_DECODE_LOG = (
    "[AGENT] Failed to decode JSON from LLM response: {exc!r} [URL: {url}]"
)
MSG_ERROR_JSON_DECODING_FAILED_WITH_URL = "[AGENT] Failed to parse LLM output: {exc} [URL: {url}]"
MSG_ERROR_API_LOG_WITH_URL = "[AGENT] OpenAI API error occurred. [URL: {url}]"
MSG_ERROR_API = "[AGENT] OpenAI API error occurred: {error}"
MSG_DEBUG_PARSED_STRUCTURED_DATA = "[AGENT] Parsed structured data: {data}"
MSG_DEBUG_API_EXCEPTION = "[AGENT] Full exception details:"
MSG_ERROR_MISSING_OPENAI_CONFIG = "Missing OpenAI config."
MSG_ERROR_MISSING_OPENAI_API_KEY = "Missing OpenAI API key."
MSG_ERROR_MISSING_OPENAI_PROJECT_ID = "Missing OpenAI project ID."
MSG_DEBUG_LLM_FIELD_SCORE_DETAILS = (
    "[AGENT] [LLM] Attempt {attempt} for {url}: score={score:.2f} | field_weights={field_weights}"
)

MSG_DEBUG_EARLY_EXIT_TRIGGERED = (
    "[AGENT] [LLM] [{url}] Early exit: no new fields added and no missing fields recovered."
)
MSG_DEBUG_EARLY_EXIT_SKIPPED = (
    "[AGENT] [LLM] [{url}] Continue retry: "
    "new_fields={new_fields}, newly_filled_missing={newly_filled_missing}"
)
MSG_DEBUG_CONTEXT_HINTS_EXTRACTED = (
    "[AGENT] [LLM] [{url}] Context hints extracted: type={page_type},"
    "meta_keys={meta_keys}, breadcrumbs_count={breadcrumbs}"
)

MSG_ERROR_MASKED_OPENAI_API_KEY = (
    "[AGENT] [LLM] OpenAI API key appearsmasked/redacted; update stored credentials."
)
MSG_DEBUG_LLM_JSON_REPAIRED = (
    "[AGENT] [LLM] [{url}]LLM output repaired and parsed after JSONDecodeError"
)

# field_utils.py
MSG_DEBUG_UNAVAILABLE_FIELDS_DETECTED = "Unavailable fields detected in raw data: {fields}"
MSG_DEBUG_NORMALIZED_KEYS = "Field keys normalized: original={original}, mapped={normalized}"


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
MSG_ERROR_LLM_RESPONSE_MALFORMED_WITH_URL = (
    "[AGENT] [LLM] LLM response missing or malformed. [URL: {url}]"
)
MSG_ERROR_LLM_RESPONSE_EMPTY_CONTENT_WITH_URL = "[AGENT] [LLM] response was None. [URL: {url}]"

MSG_ERROR_RATE_LIMIT = (
    "[AGENT] [LLM] OpenAI quota exceeded. Please check your usage and billing at "
    "https://platform.openai.com/account/usage."
)
MSG_ERROR_RATE_LIMIT_LOG = "[AGENT] [LLM] OpenAI quota exceeded."

MSG_ERROR_API_LOG = "[AGENT] [LLM] OpenAI API error occurred: {exc}"

MSG_INFO_EXTRACTION_SUCCESS_WITH_URL = "[AGENT] Extracted structured data from: {url}"
MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL = (
    "[AGENT] [LLM] Failed to validate LLM response for {url}: {exc}"
)

# __init__.py
MSG_ERROR_INVALID_AGENT_MODE = (
    "[AGENT] Invalid agent mode: '{value}'. Valid options: {valid_options}"
)
MSG_ERROR_UNHANDLED_AGENT_MODE = "[AGENT] Unhandled AGENT_MODE: {value}"


# rule_based.py
MSG_DEBUG_RULE_BASED_EXTRACTION_FAILED = (
    "[AGENT] [RULE_BASED] extraction failed to construct ScrapedItem for {url}: {error}"
)
MSG_DEBUG_RULE_BASED_START = "[AGENT] [RULE_BASED] Attempting extraction for URL: {url}"
MSG_DEBUG_RULE_BASED_TITLE = "[AGENT] [RULE_BASED] Title guessed: {title}"
MSG_DEBUG_RULE_BASED_DESCRIPTION = "[AGENT] [RULE_BASED] Description guessed: {description}"
MSG_DEBUG_RULE_BASED_PRICE = "[AGENT] [RULE_BASED] Price guessed: {price}"
MSG_DEBUG_RULE_BASED_VALIDATION_SUCCESS = (
    "[AGENT] [RULE_BASED] Validation succeeded. Returning ScrapedItem."
)
MSG_DEBUG_RULE_BASED_VALIDATION_FAILED_FIELDS = (
    "[AGENT] [RULE_BASED] Validation failed for fields: title={title!r}, "
    "description={description!r}, price={price!r}, url={url}"
)
MSG_ERROR_RULE_BASED_EXTRACTION_FAILED = "[AGENT] [RULE_BASED] Validation failed for URL: {url}"

# llm_dynamic.py
MSG_INFO_FIELD_DISCOVERY_SCORE = (
    "[AGENT] [LLM] [{url}] Field discovery score: "
    "{score:.2f} (excluding {num_unavailable} unavailable)"
)
MSG_DEBUG_LLM_PROMPT_WITH_URL = "[AGENT] [LLM] [{url}] Prompt sent to OpenAI:\n{prompt}"


# llm_dynamic_adaptive.py

MSG_DEBUG_MISSING_IMPORTANT_FIELDS = (
    "[AGENT] [LLM] Missing critical fields {fields} in first pass, retrying with recovery prompt..."
)

MSG_INFO_ADAPTIVE_EXTRACTION_SUCCESS_WITH_URL = (
    "[AGENT] [LLM] Adaptive LLM extraction succeeded for {url} with field recovery if needed."
)

MSG_DEBUG_CONTEXTUAL_HINTS_USED = (
    "[AGENT] [LLM] Using context hints for {url}: meta={meta},"
    " breadcrumbs={breadcrumbs}, url_segments={url_segments}"
)
MSG_WARN_ADAPTIVE_EXTRACTION_FAILED_AFTER_RETRIES = (
    "[AGENT] [LLM] Failed to extract sufficient fields after {attempts} adaptive attempts for {url}"
)
MSG_DEBUG_USING_BEST_CANDIDATE_FIELDS = "[AGENT] [LLM] Using best candidate with fields: {fields}"
MSG_DEBUG_LLM_RETRY_ATTEMPT = "[AGENT] [LLM] LLM retry attempt {attempt}/{total} for {url}"
MSG_WARN_LLM_RATE_LIMIT_SLEEP = (
    "[AGENT] [LLM] Rate limit hit for {url}, sleeping {delay:.1f}s as advised..."
)
MSG_DEBUG_FIELD_SCORE_PER_RETRY = (
    "[AGENT] [LLM] [{url}] Retry #{attempt}: score={score}, fields={fields}"
)
MSG_DEBUG_LLM_INITIAL_PROMPT = "[AGENT] [LLM] Initial LLM prompt for {url}:\n{prompt}"

MSG_DEBUG_LLM_RETRY_PROMPT = "[AGENT] [LLM] Retry prompt for {url} (attempt {attempt}):\n{message}"

MSG_DEBUG_FINAL_DISCOVERY_RETRY_TRIGGERED = (
    "[AGENT] [LLM] [{url}] Final discovery"
    "retry triggered (required fields complete, exploring optional fields)."
)


MSG_DEBUG_PROMPT_RETRY_MODE = (
    "[AGENT] [LLM] [{url}] Building retryprompt. Missing fields: {missing}"
)
MSG_DEBUG_PROMPT_FALLBACK_MODE = (
    "[AGENT] [LLM] [{url}] Building fallbackprompt (no missing fields)."
)


# ---------------------------------------------------------------------
# common/logging.py
# ---------------------------------------------------------------------

# streamlit_ui.py
MSG_INFO_UI_STARTED = "[UI] Streamlit UI started."
MSG_WARNING_NO_INPUT_URL = "[UI] No input URL provided."
MSG_ERROR_EXTRACTION_ABORTED = "[UI] Extraction aborted due to previous errors."

# ---------------------------------------------------------------------
# config/
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# common/logging.py
# ---------------------------------------------------------------------

MSG_INFO_LOGGING_INITIALIZED = "[LOG] Logging initialized. Logs will be written to {path}"
MSG_WARNING_LOG_FILE_FAIL = "[LOG] Failed to write log file to: {path}"

# ---------------------------------------------------------------------
# utils/
# ---------------------------------------------------------------------

# validators.py
MSG_DEBUG_SKIPPED_INVALID_URL = "[VALIDATION] Skipping invalid URL input: {url!r}"
MSG_ERROR_NOT_A_DIRECTORY = "[VALIDATION] Path {path} exists but is not a directory."
MSG_ERROR_UNSUPPORTED_OPENAI_MODEL = (
    "[VALIDATION] Unsupported OpenAI model: {model!r}. Must be one of: {valid_models}"
)
MSG_ERROR_BACKOFF_MIN_NEGATIVE = "[VALIDATION] Retry backoff min must be non-negative."
MSG_ERROR_BACKOFF_MAX_NEGATIVE = "[VALIDATION] Retry backoff max must be non-negative."
MSG_ERROR_BACKOFF_MIN_GT_MAX = "[VALIDATION] Retry backoff min must be less than or equal to max."
MSG_ERROR_RETRY_NEGATIVE = "[VALIDATION] Retry attempts must be non-negative"
MSG_ERROR_INVALID_PRICE_FORMAT = "[VALIDATION] Invalid price format: {value}"

MSG_ERROR_INVALID_AUTH0_DOMAIN = (
    "[VALIDATION] AUTH0_DOMAIN must be a valid Auth0 domain (e.g., dev-xxx.us.auth0.com)"
)
MSG_ERROR_INVALID_API_AUDIENCE = (
    "[VALIDATION] API_AUDIENCE must be a valid URL (e.g., https://api.example.com/)"
)
MSG_ERROR_INVALID_ENCRYPTION_SECRET = (
    "[VALIDATION] ENCRYPTION_SECRET must be at least {value} characters long"
)
MSG_ERROR_INVALID_AUTH0_ALGORITHMS = (
    "[VALIDATION] Invalid auth0_algorithms {algo}. Optionas are {valid_options}"
)
MSG_ERROR_EMPTY_AUTH0_ALGORITHMS = "[VALIDATION] auth0_algorithms must not be empty"
MSG_ERROR_UNEXPECTED_EXCEPTION = "[VALIDATION] Unexpected error during token validation."
MSG_INFO_USER_AUTHORIZED = "[VALIDATION] User successfully authenticated and authorized."
MSG_ERROR_USER_SCOPES_TYPE = (
    "[VALIDATION] Expected 'user_scopes' to be a list of strings, got {type(user_scopes)}"
)


MSG_ERROR_PRELOADING_JWKS = "[VALIDATION] Error occurred while preloading JWKS from Auth0"
