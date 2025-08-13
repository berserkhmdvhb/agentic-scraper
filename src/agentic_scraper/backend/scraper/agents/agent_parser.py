# src/agentic_scraper/backend/scraper/agents/agent_parsing.py
"""
Parsing and repair helpers for LLM JSON output.

This module is intentionally separate from agent_helpers to keep parsing concerns isolated,
reduce import footprint (no Playwright/BS4 here), and make unit testing simpler.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, cast

from agentic_scraper.backend.config.constants import (
    JSON_DOUBLE_QUOTE_THRESHOLD,
    JSON_SINGLE_QUOTE_THRESHOLD,
)
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_LLM_JSON_HEAD_TAIL,
    MSG_DEBUG_LLM_JSON_REPAIRED,
    MSG_DEBUG_LLM_JSON_TRUNCATION_REPAIR_APPLIED,
    MSG_ERROR_JSON_DECODING_FAILED_WITH_URL,
    MSG_ERROR_LLM_JSON_PARSE_GIVING_UP_WITH_URL,
)

logger = logging.getLogger(__name__)

__all__ = ["parse_llm_response"]

if TYPE_CHECKING:
    from agentic_scraper.backend.core.settings import Settings


# Precompiled regex to mask JSON string literals (handles escaped quotes)
STRING_LITERAL_RE = re.compile(r'"(?:\\.|[^"\\])*"')


def parse_llm_response(content: str, url: str, settings: Settings) -> dict[str, Any] | None:
    """
    Parse best-effort JSON from an LLM response WITHOUT triggering any re-asks.
    Strategy:
      1) Fast path: json.loads on the whole content.
      2) Extract the largest balanced JSON object from the text and parse that.
      3) Apply minimal truncation repair (close unterminated string/brackets) and parse.
      4) Lightweight sanitation (strip fences, trim trailing commas, quote bare keys) and parse.
    If all fail, return None.
    """
    # 1) Fast path
    try:
        return cast("dict[str, Any]", json.loads(content))
    except json.JSONDecodeError as e:
        logger.warning(MSG_ERROR_JSON_DECODING_FAILED_WITH_URL.format(exc=e, url=url))
        if settings.is_verbose_mode:
            head, tail = content[:200], content[-300:]
            logger.debug(
                MSG_DEBUG_LLM_JSON_HEAD_TAIL.format(
                    url=url, head=head, tail=tail, length=len(content)
                )
            )

    # 2) Extract the largest balanced JSON object substring and try that
    extracted = _extract_largest_balanced_json_object(content)
    if extracted:
        try:
            return cast("dict[str, Any]", json.loads(extracted))
        except json.JSONDecodeError:
            pass  # fall through

    # 3) Truncation-aware close of quotes/brackets
    balanced = _balance_and_close_json(content)
    if balanced is not None:
        try:
            logger.debug(MSG_DEBUG_LLM_JSON_TRUNCATION_REPAIR_APPLIED.format(url=url))
            return cast("dict[str, Any]", json.loads(balanced))
        except json.JSONDecodeError:
            pass

    # 4) Lightweight sanitation and retry parse
    fixed = _try_fix_and_parse_json(content)
    if fixed is not None:
        logger.debug(MSG_DEBUG_LLM_JSON_REPAIRED.format(url=url))
        return fixed

    if settings.is_verbose_mode:
        logger.debug(
            MSG_ERROR_LLM_JSON_PARSE_GIVING_UP_WITH_URL.format(url=url, exc="JSONDecodeError")
        )
    return None


# ---- internal helpers -----------------------------------------------------


def _mask_strings(s: str) -> str:
    """Replace JSON string literals with empty quotes to simplify brace scanning."""
    return STRING_LITERAL_RE.sub('""', s)


def _scan_json_boundaries(s: str) -> tuple[int | None, int | None]:
    """
    Return (start_index, best_end_index) for the largest top-level JSON object.
    Scans a version of the text with string literals masked, so braces inside
    strings are ignored.
    """
    masked = _mask_strings(s)
    start: int | None = None
    best_end: int | None = None
    depth = 0

    for i, ch in enumerate(masked):
        if ch == "{":
            if depth == 0 and start is None:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    best_end = i

    return start, best_end


def _extract_largest_balanced_json_object(text: str) -> str | None:
    """Return substring for the largest balanced {...} object, or None."""
    start, best_end = _scan_json_boundaries(text)
    if start is not None and best_end is not None and best_end > start:
        return text[start : best_end + 1]
    return None


def _count_unclosed_structures(s: str) -> tuple[int, int]:
    """
    Count unclosed { } and [ ] at the end of the payload (ignoring braces inside strings).
    Returns (open_braces, open_brackets).
    """
    masked = _mask_strings(s)
    open_braces = 0
    open_brackets = 0

    for ch in masked:
        if ch == "{":
            open_braces += 1
        elif ch == "}":
            open_braces = max(0, open_braces - 1)
        elif ch == "[":
            open_brackets += 1
        elif ch == "]":
            open_brackets = max(0, open_brackets - 1)

    return open_braces, open_brackets


def _balance_and_close_json(bad_json: str) -> str | None:
    """
    Minimally close an unterminated string/object/array at the end of the payload.
    - If EOF occurs inside a string, close the quote (by appending a double quote).
    - Balance braces/brackets by appending the minimal number of closing ] and }.
    """
    s = bad_json.rstrip()
    if "{" not in s and "[" not in s and '"' not in s:
        return None

    # Heuristic: odd number of unescaped quotes => inside a string at EOF
    unescaped_quote_count = len(re.findall(r'(?<!\\)"', s))
    ended_inside_string = (unescaped_quote_count % 2) == 1

    open_braces, open_brackets = _count_unclosed_structures(s)

    tail: list[str] = []
    if ended_inside_string:
        tail.append('"')
    tail.extend("]" * open_brackets)
    tail.extend("}" * open_braces)

    if not tail:
        return None
    return s + "".join(tail)


def _try_fix_and_parse_json(bad_json: str) -> dict[str, Any] | None:
    """
    Attempt to repair common formatting issues in LLM JSON and re-parse.
    Fixes:
        - Strip markdown fences / leading-trailing prose (clamp to outermost braces if present)
        - Remove trailing commas
        - Quote unquoted property names (conservative)
        - (Avoid global single-quote -> double-quote unless clearly needed)
    """
    cleaned = bad_json.strip()
    # Remove ```json fences if present
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    if cleaned.endswith("```"):
        cleaned = re.sub(r"\s*```$", "", cleaned)

    # Clamp to first '{' and last '}' if both exist (drop stray prose)
    if "{" in cleaned and "}" in cleaned:
        first = cleaned.find("{")
        last = cleaned.rfind("}")
        if first < last:
            cleaned = cleaned[first : last + 1]

    # Remove trailing commas before } or ]
    cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)

    # Quote unquoted keys conservatively (only when not inside strings)
    cleaned = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*):", r'\1"\2"\3:', cleaned)
    # Only if there are almost no double quotes at all (likely single-quoted JSON), then swap
    double_quote_count = cleaned.count('"')
    single_quote_count = cleaned.count("'")
    if (
        double_quote_count < JSON_DOUBLE_QUOTE_THRESHOLD
        and single_quote_count > JSON_SINGLE_QUOTE_THRESHOLD
    ):
        cleaned = cleaned.replace("'", '"')

    try:
        return cast("dict[str, Any]", json.loads(cleaned))
    except json.JSONDecodeError:
        return None
