"""
Shared utility functions for LLM-based scraping agents in AgenticScraper.

Responsibilities:
- Parse and (lightly) repair LLM JSON output before validation.
- Validate structured data against internal schemas and log summaries.
- Capture screenshots (best-effort) for debugging/archiving.
- Extract contextual hints from HTML/URL to enrich LLM prompts.
- Score non-empty fields and decide on early-exit across retries.
- Normalize and verify OpenAI credentials (defense-in-depth).

Public API:
- `parse_llm_response`: Safe JSON parse with common-repair fallback.
- `capture_optional_screenshot`: Best-effort screenshot capture.
- `handle_openai_exception`: Verbosity-aware OpenAI error logging.
- `log_structured_data`: Debug log + optional JSON dump of fields.
- `extract_context_hints`: HTML/URL breadcrumbs/meta hints.
- `try_validate_scraped_item`: Schema validation → ScrapedItem | None.
- `score_and_log_fields`: Weighted field scoring with debug logs.
- `retrieve_openai_credentials`: Validate & extract API key/project.
- `should_exit_early`: Retry loop short-circuit decision helper.

Operational:
- Concurrency: All helpers are pure or async and safe to call from worker tasks.
- Logging: Uses message constants; verbose mode increases detail and dumps JSON.
- Privacy: Explicitly avoids logging secrets; detects masked API keys.

Usage:
    from agentic_scraper.backend.scraper.agents.agent_helpers import (
        parse_llm_response, try_validate_scraped_item
    )

    data = parse_llm_response(llm_text, url, settings)
    item = try_validate_scraped_item(data or {}, url, settings)

Notes:
- JSON “repair” aims for common LLM artifacts only; it is intentionally conservative.
- Screenshotting requires Playwright runtime; failures are logged and ignored.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError
from pydantic import ValidationError

from agentic_scraper.backend.config.aliases import (
    APIErrorT,
    OpenAIErrorT,
    RateLimitErrorT,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_API_EXCEPTION,
    MSG_DEBUG_CONTEXT_HINTS_EXTRACTED,
    MSG_DEBUG_EARLY_EXIT_SKIPPED,
    MSG_DEBUG_EARLY_EXIT_TRIGGERED,
    MSG_DEBUG_LLM_FIELD_SCORE_DETAILS,
    MSG_DEBUG_LLM_JSON_DUMP_SAVED,
    MSG_DEBUG_LLM_JSON_REPAIRED,
    MSG_DEBUG_PARSED_STRUCTURED_DATA,
    MSG_DEBUG_USING_BEST_CANDIDATE_FIELDS,
    MSG_ERROR_API,
    MSG_ERROR_API_LOG_WITH_URL,
    MSG_ERROR_JSON_DECODING_FAILED_WITH_URL,
    MSG_ERROR_LLM_JSON_DECODE_LOG,
    MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL,
    MSG_ERROR_MASKED_OPENAI_API_KEY,
    MSG_ERROR_MISSING_OPENAI_API_KEY,
    MSG_ERROR_MISSING_OPENAI_CONFIG,
    MSG_ERROR_MISSING_OPENAI_PROJECT_ID,
    MSG_ERROR_OPENAI_UNEXPECTED,
    MSG_ERROR_OPENAI_UNEXPECTED_LOG_WITH_URL,
    MSG_ERROR_RATE_LIMIT_DETAIL,
    MSG_ERROR_RATE_LIMIT_LOG_WITH_URL,
    MSG_ERROR_SCREENSHOT_FAILED_WITH_URL,
    MSG_INFO_ADAPTIVE_EXTRACTION_SUCCESS_WITH_URL,
)
from agentic_scraper.backend.config.types import OpenAIConfig
from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.agents.field_utils import FIELD_WEIGHTS, score_nonempty_fields
from agentic_scraper.backend.scraper.schemas import ScrapedItem
from agentic_scraper.backend.scraper.screenshotter import capture_screenshot

logger = logging.getLogger(__name__)

__all__ = [
    "capture_optional_screenshot",
    "extract_context_hints",
    "handle_openai_exception",
    "log_structured_data",
    "parse_llm_response",
    "retrieve_openai_credentials",
    "score_and_log_fields",
    "try_validate_scraped_item",
]

# ---------------------------------------------------------------------------
# Secret masking detection (defense-in-depth)
# ---------------------------------------------------------------------------

MASK_CHARS: set[str] = {"*", "•", "●", "·"}
MASK_WORDS: set[str] = {"redacted", "masked", "hidden"}


def _is_masked_secret(s: str | None) -> bool:
    """
    Heuristically detect masked/redacted secrets.

    Args:
        s (str | None): Candidate secret.

    Returns:
        bool: True if the value looks masked (e.g., contains '****' or 'redacted').

    Notes:
        - This is best-effort to prevent accidentally accepting placeholder keys.
    """
    if not isinstance(s, str) or not s:
        return False
    if any(ch in s for ch in MASK_CHARS):
        return True
    ls = s.lower()
    return any(w in ls for w in MASK_WORDS)


# ─────────────────────────────────────────────────────────────────────────────
# Low-level helpers: JSON parsing, screenshot, exception handling
# ─────────────────────────────────────────────────────────────────────────────


def parse_llm_response(content: str, url: str, settings: Settings) -> dict[str, Any] | None:
    """
    Parse LLM JSON content safely, with conservative auto-repair on failure.

    Args:
        content (str): JSON string returned by the LLM (may include minor formatting issues).
        url (str): The source URL being processed (used for logs).
        settings (Settings): Runtime config controlling verbosity and dumps.

    Returns:
        dict[str, Any] | None: Parsed dictionary if successful, else None.

    Notes:
        - On initial parse failure, attempts cheap repairs (e.g., strip ``` fences,
          fix quotes/trailing commas/unquoted keys) before giving up.
        - Does not raise; callers should handle None.
    """
    try:
        return cast("dict[str, Any]", json.loads(content))
    except json.JSONDecodeError as e:
        logger.warning(MSG_ERROR_JSON_DECODING_FAILED_WITH_URL.format(exc=e, url=url))
        if settings.is_verbose_mode:
            logger.debug(MSG_ERROR_LLM_JSON_DECODE_LOG.format(exc=e, url=url))

        # Attempt repair of common LLM formatting artifacts.
        fixed = _try_fix_and_parse_json(content)
        if fixed is not None:
            logger.debug(MSG_DEBUG_LLM_JSON_REPAIRED.format(url=url))
            return fixed

        return None


async def capture_optional_screenshot(url: str, settings: Settings) -> str | None:
    """
    Best-effort screenshot capture; returns None on failure.

    Args:
        url (str): The URL to capture.
        settings (Settings): Runtime config (screenshot directory, etc.).

    Returns:
        str | None: Path to saved screenshot if successful, otherwise None.

    Notes:
        - Exceptions from Playwright or filesystem are swallowed and logged.
        - Keeps pipeline resilient when headless browser is unavailable.
    """
    try:
        return await capture_screenshot(url, output_dir=Path(settings.screenshot_dir))
    except (PlaywrightError, OSError, ValueError):
        logger.warning(MSG_ERROR_SCREENSHOT_FAILED_WITH_URL.format(url=url))
        return None


def handle_openai_exception(e: OpenAIErrorT, url: str, settings: Settings) -> None:
    """
    Log OpenAI-related errors with verbosity-aware detail.

    Args:
        e (OpenAIErrorT): The OpenAI exception raised.
        url (str): The URL that triggered the exception.
        settings (Settings): Runtime config for verbosity.

    Returns:
        None

    Notes:
        - Keeps non-verbose logs concise, but adds details when verbose.
    """
    if isinstance(e, RateLimitErrorT):
        logger.warning(MSG_ERROR_RATE_LIMIT_LOG_WITH_URL.format(url=url))
        if settings.is_verbose_mode:
            logger.debug(MSG_ERROR_RATE_LIMIT_DETAIL.format(error=e))
    elif isinstance(e, APIErrorT):
        logger.warning(MSG_ERROR_API_LOG_WITH_URL.format(url=url))
        if settings.is_verbose_mode:
            logger.debug(MSG_DEBUG_API_EXCEPTION)
            logger.debug(MSG_ERROR_API.format(error=e))
    else:
        logger.warning(MSG_ERROR_OPENAI_UNEXPECTED_LOG_WITH_URL.format(url=url))
        if settings.is_verbose_mode:
            logger.debug(MSG_ERROR_OPENAI_UNEXPECTED.format(error=e))


# ─────────────────────────────────────────────────────────────────────────────
# Logging and debugging utilities
# ─────────────────────────────────────────────────────────────────────────────


def log_structured_data(data: dict[str, Any], settings: Settings) -> None:
    """
    Log a compact summary of structured data and optionally dump full JSON.

    Args:
        data (dict[str, Any]): Validated structured data from the LLM.
        settings (Settings): Runtime config (controls verbose mode and JSON dump).

    Returns:
        None

    Notes:
        - Uses `settings.verbose` rather than `is_verbose_mode` to honor explicit user intent.
        - Dumps full JSON to `dump_llm_json_dir` when configured.
    """
    # Honor explicit verbose flag to avoid accidental data dumps.
    if not getattr(settings, "verbose", False):
        return

    # Summarize values without leaking large bodies.
    summary = {
        k: f"str({len(v)})" if isinstance(v, str) else "None" if v is None else type(v).__name__
        for k, v in data.items()
    }
    logger.debug(MSG_DEBUG_PARSED_STRUCTURED_DATA.format(data=summary))

    # Optional structured dump for debugging/inspection.
    if settings.dump_llm_json_dir:
        dump_dir = Path(settings.dump_llm_json_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=timezone.utc).isoformat().replace(":", "_")
        filename = f"{timestamp}.json"
        dump_path = dump_dir / filename
        with dump_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.debug(MSG_DEBUG_LLM_JSON_DUMP_SAVED.format(path=str(dump_path)))


# ─────────────────────────────────────────────────────────────────────────────
# LLM prompt context extraction
# ─────────────────────────────────────────────────────────────────────────────


def extract_context_hints(html: str, url: str) -> dict[str, str]:
    """
    Extract simple contextual hints from HTML and URL to enrich prompts.

    Args:
        html (str): Raw HTML content of the page.
        url (str): Source URL of the page.

    Returns:
        dict[str, str]: Compact summary of meta tags, breadcrumbs, URL segments, etc.

    Notes:
        - Prioritizes a small, stable set of hints to reduce token usage.
        - Deduplicates breadcrumbs across common class/id patterns.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Small curated set of meta properties likely useful for prompts.
    useful_meta_keys = {
        "title",
        "description",
        "keywords",
        "author",
        "og:title",
        "og:description",
        "og:site_name",
        "og:type",
        "article:published_time",
        "twitter:title",
        "twitter:description",
    }
    meta_tags = {
        k: v
        for tag in soup.find_all("meta")
        if (
            (k := tag.get("name") or tag.get("property")) in useful_meta_keys
            and (v := tag.get("content"))
        )
    }
    meta_summary = "; ".join(f"{k}={v}" for k, v in meta_tags.items())

    # Breadcrumb heuristics across typical class/id patterns.
    breadcrumb_selectors = [
        '[class*="breadcrumb"]',
        '[id*="breadcrumb"]',
        '[class*="breadcrumbs"]',
        '[id*="breadcrumbs"]',
    ]
    breadcrumb_texts: list[str] = []
    seen_breadcrumbs = set()
    for sel in breadcrumb_selectors:
        for elem in soup.select(sel):
            text = elem.get_text(strip=True)
            if text and text not in seen_breadcrumbs:
                breadcrumb_texts.append(text)
                seen_breadcrumbs.add(text)

    # ARIA breadcrumb fallback.
    if not breadcrumb_texts:
        nav_breadcrumb = soup.select_one("nav[aria-label='breadcrumb']")
        if nav_breadcrumb:
            breadcrumb_texts.append(nav_breadcrumb.get_text(strip=True))

    # Basic URL-derived hints.
    breadcrumbs = " > ".join(breadcrumb_texts)
    parsed = urlparse(url)
    url_segments = " / ".join(filter(None, parsed.path.split("/")))
    domain = parsed.netloc.lower()
    last_segment = parsed.path.rstrip("/").split("/")[-1]

    # Title/H1 as lightweight signals.
    page_title = soup.title.string.strip() if soup.title and soup.title.string else ""
    h1 = soup.find("h1")
    first_h1 = h1.get_text(strip=True) if h1 else ""

    # ─── Naive Page Type Inference ─────────────────────────────────────────────
    # Keeps the prompt compact while hinting at likely schema.
    lower_url = url.lower()
    lower_title = page_title.lower()
    lower_h1 = first_h1.lower()
    combined = f"{lower_url} {lower_title} {lower_h1}"

    if "product" in combined or "shop" in combined:
        page_type = "product"
    elif "job" in combined or "career" in combined or "apply" in combined:
        page_type = "job"
    elif "blog" in combined or "post" in combined or "article" in combined:
        page_type = "blog"
    else:
        page_type = "unknown"

    logger.debug(
        MSG_DEBUG_CONTEXT_HINTS_EXTRACTED.format(
            url=url,
            page_type=page_type,
            meta_keys=len(meta_tags),
            breadcrumbs=len(breadcrumb_texts),
        )
    )
    return {
        "meta": meta_summary,
        "breadcrumbs": breadcrumbs,
        "url_segments": url_segments,
        "context_domain": domain,
        "url_last_segment": last_segment,
        "page_title": page_title,
        "first_h1": first_h1,
        "page": page_type,  # consumed by prompt_helpers.py
    }


# ─────────────────────────────────────────────────────────────────────────────
# Data validation and retry scoring
# ─────────────────────────────────────────────────────────────────────────────


def try_validate_scraped_item(
    data: dict[str, Any], url: str, settings: Settings
) -> ScrapedItem | None:
    """
    Validate `data` against `ScrapedItem` and log outcome.

    Args:
        data (dict[str, Any]): Raw JSON-like dict from LLM output.
        url (str): Source URL (for logs).
        settings (Settings): Runtime config used for logging.

    Returns:
        ScrapedItem | None: Validated item, or None when validation fails.

    Notes:
        - Emits a concise success log; dumps fields when verbose.
    """
    if not data:
        return None

    try:
        item = ScrapedItem.model_validate(data)
    except ValidationError as ve:
        logger.warning(MSG_ERROR_LLM_VALIDATION_FAILED_WITH_URL.format(url=url, exc=ve))
        return None
    else:
        logger.info(MSG_INFO_ADAPTIVE_EXTRACTION_SUCCESS_WITH_URL.format(url=url))
        logger.debug(MSG_DEBUG_USING_BEST_CANDIDATE_FIELDS.format(fields=list(data.keys())))
        log_structured_data(item.model_dump(mode="json"), settings)
        return item


def score_and_log_fields(
    fields: set[str],
    attempt: int,
    url: str,
    raw_data: dict[str, Any] | None = None,
) -> float:
    """
    Compute a weighted completeness score for fields and log details.

    Args:
        fields (set[str]): Field names considered in the attempt.
        attempt (int): Attempt counter (1-based).
        url (str): Source URL for logs.
        raw_data (dict[str, Any] | None): Optional raw key→value mapping; used to
            determine non-emptiness and compute the score precisely.

    Returns:
        float: Normalized score in [0.0, 1.0].

    Notes:
        - Uses project weights (FIELD_WEIGHTS) and clamps to [0,1] for stability.
    """
    nonempty_keys = {
        k
        for k, v in (raw_data.items() if raw_data else [(f, "nonempty") for f in fields])
        if v not in [None, ""]
    }

    # Base score may exceed 1.0 depending on weights; normalize to [0, 1].
    base_score = score_nonempty_fields(raw_data or dict.fromkeys(nonempty_keys, "nonempty"))
    score = max(0.0, min(1.0, float(base_score)))

    logger.debug(
        MSG_DEBUG_LLM_FIELD_SCORE_DETAILS.format(
            attempt=attempt,
            url=url,
            score=score,
            field_weights={k: FIELD_WEIGHTS.get(k, 0.3) for k in nonempty_keys},
        )
    )

    return score


def retrieve_openai_credentials(config: OpenAIConfig | None) -> tuple[str, str]:
    """
    Validate and extract OpenAI credentials from `OpenAIConfig`.

    Args:
        config (OpenAIConfig | None): The OpenAI credentials configuration.

    Returns:
        tuple[str, str]: `(api_key, project_id)` if valid.

    Raises:
        ValueError: If `config` is None, fields are missing, or API key looks masked.

    Notes:
        - Masked detection prevents accidentally accepting placeholders from UIs.
    """
    if config is None:
        raise ValueError(MSG_ERROR_MISSING_OPENAI_CONFIG)
    if not config.api_key:
        raise ValueError(MSG_ERROR_MISSING_OPENAI_API_KEY)
    # Defensive: refuse obviously masked keys (e.g., "sk-****").
    if _is_masked_secret(config.api_key):
        raise ValueError(MSG_ERROR_MASKED_OPENAI_API_KEY)
    if not config.project_id:
        raise ValueError(MSG_ERROR_MISSING_OPENAI_PROJECT_ID)
    return config.api_key, config.project_id


def should_exit_early(
    *,
    item: ScrapedItem | None,
    raw_data: dict[str, Any],
    best_fields: dict[str, Any] | None,
    missing: set[str],
    url: str,
) -> bool:
    """
    Decide whether retry loop should stop based on marginal progress.

    Args:
        item (ScrapedItem | None): The current validated item (if any).
        raw_data (dict[str, Any]): Normalized fields from the current attempt.
        best_fields (dict[str, Any] | None): Best fields across previous attempts.
        missing (set[str]): Required fields still missing.
        url (str): Source URL (for logs).

    Returns:
        bool: True to stop retrying, False to continue.

    Notes:
        - First success never triggers early exit (always retry once).
        - Stops when no new fields are gained and no required field was newly filled.
    """
    if item is None:
        return False

    # Prevent early exit on first result (always retry once).
    if not best_fields:
        return False

    previous_keys = set(best_fields)
    current_keys = set(raw_data)
    new_fields = current_keys - previous_keys
    newly_filled_missing = missing & new_fields

    should_stop = not new_fields and not newly_filled_missing

    if should_stop:
        logger.debug(MSG_DEBUG_EARLY_EXIT_TRIGGERED.format(url=url))
    else:
        logger.debug(
            MSG_DEBUG_EARLY_EXIT_SKIPPED.format(
                url=url,
                new_fields=new_fields,
                newly_filled_missing=newly_filled_missing,
            )
        )

    return should_stop


def _try_fix_and_parse_json(bad_json: str) -> dict[str, Any] | None:
    """
    Attempt to repair common LLM JSON formatting issues and re-parse.

    Fixes:
        - Strips ```json fences.
        - Single quotes → double quotes.
        - Trailing commas before ']' or '}'.
        - Quotes unquoted property names (`foo: 1` → `"foo": 1`).

    Args:
        bad_json (str): Original malformed JSON text.

    Returns:
        dict[str, Any] | None: Parsed JSON if successful, else None.

    Notes:
        - Intentionally conservative; avoids heavy-weight “JSONC” parsing.
    """
    cleaned = bad_json.strip().removeprefix("```json").removesuffix("```").strip()

    # Replace single quotes with double quotes (common markdown/LLM artifact).
    cleaned = cleaned.replace("'", '"')

    # Remove trailing commas before object/array close.
    cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)

    # Quote unquoted keys: { a: 1 } → { "a": 1 }.
    cleaned = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*):", r'\1"\2"\3:', cleaned)

    try:
        return cast("dict[str, Any]", json.loads(cleaned))
    except json.JSONDecodeError:
        return None
