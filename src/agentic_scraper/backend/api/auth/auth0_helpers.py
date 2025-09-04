"""
Auth0 JWKS and JWT verification helpers.

Responsibilities:
- Fetch and cache Auth0 JWKS (JSON Web Key Set) for signature verification.
- Verify and decode JWTs against issuer/audience using python-jose.
- Provide a uniform helper to raise `HTTPException` with consistent logging.

Public API:
- `verify_jwt`: Validate, verify, and decode a JWT using the cached JWKS.
- `JWKSCache`: Lightweight in-memory JWKS cache with TTL and retries.
- `raise_http_exception`: Raise `HTTPException` while logging the root cause.

Config:
- AUTH0_ISSUER: Must include a trailing slash (e.g., "https://tenant.us.auth0.com/").
- AUTH0_API_AUDIENCE: Trailing slash is deployment-dependent (do not force one).
- AUTH0_ALGORITHMS: Allowed JWT algorithms (e.g., ["RS256"]).
- LOGGING_VERBOSITY / settings.verbose: Controls occasional payload sampling.

Operational:
- Concurrency: Process-local cache; no cross-process coordination. Safe duplicate reads.
- Caching/TTL: JWKS cached for 1 hour to reduce latency and Auth0 round-trips.
- Retries: Transient JWKS fetch failures retried up to RETRY_LIMIT with jittered backoff.
- Logging: Message strings come from `config/messages.py` for consistency.

Usage:
    from agentic_scraper.backend.api.auth.auth0_helpers import verify_jwt
    payload = await verify_jwt(token)

Notes:
- No I/O happens at import; network access occurs only when fetching JWKS.
- Surface network/JWKS failures as 503 (distinguish from 401 auth failures).
- Keep `AUTH0_ISSUER` trailing slash; audience trailing slash may vary by setup.
"""

import asyncio
import itertools
import logging
from secrets import randbelow
from time import time
from typing import Any, cast

import httpx
from fastapi import HTTPException
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_CURRENT_ISSUER,
    MSG_DEBUG_DECODED_TOKEN,
    MSG_DEBUG_FETCHING_JWKS,
    MSG_DEBUG_JWKS_FETCHED,
    MSG_ERROR_FETCHING_JWKS,
    MSG_ERROR_INVALID_JWT_HEADER,
    MSG_ERROR_JWT_EXPIRED,
    MSG_ERROR_JWT_UNEXPECTED,
    MSG_ERROR_JWT_VERIFICATION,
    MSG_ERROR_NO_RSA_KEY,
    MSG_INFO_DECODING_JWT,
    MSG_INFO_RETRYING,
)
from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.backend.utils.validators import validate_jwt_token_str

logger = logging.getLogger(__name__)
settings = get_settings()

# Use a simple counter to sample (debug) logs and avoid excessive payload logging under load.
_auth_log_counter = itertools.count()

# Retry limit for JWKS fetch attempts (total tries = RETRY_LIMIT + 1).
# Example: RETRY_LIMIT = 2 -> attempts at indexes 0, 1, 2 (max three tries).
RETRY_LIMIT = 2


def raise_http_exception(status_code: int, detail: str, error: Exception) -> None:
    """
    Raise an `HTTPException` with consistent error logging.

    Args:
        status_code (int): HTTP status code to return to the client.
        detail (str): Human-readable error message for the response body.
        error (Exception): The original exception to chain for traceback context.

    Returns:
        None

    Raises:
        HTTPException: Always raised with the provided status code and detail.

    Notes:
        - Uses `logger.exception` to include traceback context in logs.
        - Keeps the actual response body stable and non-leaky.
    """
    logger.exception(detail)
    raise HTTPException(status_code=status_code, detail=detail) from error


class JWKSCache:
    """
    In-memory, time-bounded cache for Auth0 JWKS.

    The cache reduces repeated network calls when verifying many tokens and
    introduces a small retry/backoff strategy for robustness.

    Attributes:
        jwks_cache (list[dict[str, Any]] | None): Cached JWKS keys or `None`.
        cache_timestamp (float | None): Epoch seconds when cache was set.
        cache_ttl (int): Time-to-live (seconds) for the JWKS cache. Defaults to 3600.

    Notes:
        - Fetches are retried on transient HTTP errors up to `RETRY_LIMIT`.
        - Jittered backoff (1-5s) is applied between attempts to avoid stampedes.
        - This cache is process-local and unsynchronized by design.
          Duplicate fetches across workers are harmless (idempotent reads).
    """

    def __init__(self) -> None:
        # Cached JWKS payload (list of JWK dicts). `None` means "not yet fetched".
        self.jwks_cache: list[dict[str, Any]] | None = None
        # Timestamp (seconds) when the cache was last filled; used to enforce TTL.
        self.cache_timestamp: float | None = None
        self.cache_ttl = 3600  # 1 hour TTL

    async def get_jwks(self) -> list[dict[str, Any]]:
        """
        Retrieve (and cache) the Auth0 JWKS keys.

        Returns:
            list[dict[str, Any]]: A list of JWKS key dictionaries suitable
            for constructing RSA public keys to verify JWT signatures.

        Raises:
            HTTPException: If fetching the JWKS fails after all retry attempts.

        Notes:
            - Returns cached value when TTL is still valid.
            - Uses a short-lived HTTP client per attempt to avoid reuse issues.
        """
        # Fast-path: honor TTL if we have a recent cached copy.
        if (
            self.jwks_cache
            and self.cache_timestamp
            and (time() - self.cache_timestamp < self.cache_ttl)
        ):
            return self.jwks_cache

        # Auth0 issuer must include trailing slash; append well-known suffix for JWKS.
        url = f"{settings.auth0_issuer}.well-known/jwks.json"
        logger.debug(MSG_DEBUG_CURRENT_ISSUER.format(issuer=url))

        attempt = 0
        while attempt <= RETRY_LIMIT:
            try:
                logger.debug(MSG_DEBUG_FETCHING_JWKS.format(url=url))
                # Use a short-lived client per attempt to avoid connection reuse issues.
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    # Spec-compliant JWKS responses contain a "keys" array; default to [].
                    jwks = response.json().get("keys", [])
                    logger.info(MSG_DEBUG_JWKS_FETCHED.format(num_keys=len(jwks)))
                    # Cache the keys and the moment we fetched them.
                    self.jwks_cache = jwks
                    self.cache_timestamp = time()
                    # `cast` is for type-checkers; at runtime it's a no-op.
                    return cast("list[dict[str, Any]]", jwks)

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                # Network or HTTP protocol issues; safe to retry with backoff.
                logger.exception(MSG_ERROR_FETCHING_JWKS)
                if attempt < RETRY_LIMIT:
                    logger.info(
                        MSG_INFO_RETRYING.format(
                            attempt=attempt + 1,
                            retry_limit=RETRY_LIMIT + 1,
                        )
                    )
                    # Jittered sleep (1-5s) reduces thundering herd if many workers retry.
                    await asyncio.sleep(randbelow(5) + 1)
                else:
                    # Surface as 503 to distinguish infra issues from 401s due to bad tokens.
                    raise_http_exception(503, MSG_ERROR_FETCHING_JWKS, e)

            except Exception as e:
                # Defensive catch-all for unexpected parsing/runtime issues.
                logger.exception(MSG_ERROR_FETCHING_JWKS)
                raise_http_exception(503, MSG_ERROR_FETCHING_JWKS, e)

            # Increment after each try; success paths return earlier.
            attempt += 1

        # Defensive fallback: unreachable due to raises above; kept for type-checkers.
        return []


# Shared instance to avoid re-fetching across calls in the same process.
# Memory footprint is small; TTL keeps keys fresh and reduces Auth0 calls.
jwks_cache_instance = JWKSCache()


async def verify_jwt(token: str) -> dict[str, Any]:
    """
    Validate, verify, and decode a JWT using Auth0 JWKS.

    Steps:
        1. Validate the incoming token string shape.
        2. Parse unverified headers to select the appropriate JWKS key by `kid`.
        3. Fetch JWKS (cached) and construct an RSA key.
        4. Decode and verify claims (`exp`, `aud`, `iss`) using `python-jose`.

    Args:
        token (str): The raw bearer token (JWT) supplied by the client.

    Returns:
        dict[str, Any]: The decoded JWT payload if verification succeeds.

    Raises:
        HTTPException:
            - 401 for invalid header, expired token, signature/claims errors,
              or unexpected token format.
            - 503 for JWKS retrieval failures (propagated from `JWKSCache`).

    Notes:
        - Logs decoded payload rarely to avoid leaking sensitive data; gated by verbosity
          and a simple counter to sample 1 out of N events.
    """
    try:
        # Basic structural validation / strip common "Bearer " prefixes, etc.
        token = validate_jwt_token_str(token)

        # Peek at headers to locate the correct key via "kid" without verifying yet.
        unverified_header = jwt.get_unverified_header(token)
        if not unverified_header:
            raise_http_exception(
                401, MSG_ERROR_INVALID_JWT_HEADER, ValueError("Invalid JWT header")
            )

        # Retrieve (or reuse) JWKS; may perform network I/O if cache is cold/expired.
        jwks = await jwks_cache_instance.get_jwks()

        # Select the exact RSA key by Key ID (kid) advertised in the token header.
        rsa_key: dict[str, Any] = {}
        for key in jwks:
            if key["kid"] == unverified_header["kid"]:
                # Minimal subset required by python-jose to construct the RSA public key.
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            # No matching key: either token header is stale or JWKS not in sync.
            raise_http_exception(
                401,
                MSG_ERROR_NO_RSA_KEY.format(kid=unverified_header["kid"]),
                ValueError("No matching RSA key"),
            )

        # Signature and claims verification:
        # - verify_exp=True enforces token expiration.
        # - audience/issuer are matched against our configured values.
        logger.debug(MSG_INFO_DECODING_JWT)
        decoded_token = jwt.decode(
            token,
            rsa_key,
            options={"verify_exp": True},
            algorithms=settings.auth0_algorithms,
            audience=settings.auth0_api_audience,
            issuer=settings.auth0_issuer,
        )

        # Sample payload logging to reduce verbosity and avoid leaking sensitive info too often.
        if next(_auth_log_counter) % 50 == 0 and settings.verbose:
            logger.debug(MSG_DEBUG_DECODED_TOKEN.format(decoded_token=decoded_token))

        # Help static checkers; python-jose returns a Mapping-like object.
        return cast("dict[str, Any]", decoded_token)

    except ExpiredSignatureError as e:
        # Distinguish expiration from other JWT errors for clearer telemetry.
        raise_http_exception(401, MSG_ERROR_JWT_EXPIRED.format(error=str(e)), e)
    except JWTError as e:
        # Covers signature mismatch, audience/issuer problems, malformed segments, etc.
        raise_http_exception(401, MSG_ERROR_JWT_VERIFICATION.format(error=str(e)), e)
    except (ValueError, TypeError) as e:
        # Input shape issues or type errors during validation/parsing.
        raise_http_exception(401, MSG_ERROR_JWT_UNEXPECTED.format(error=str(e)), e)

    # Defensive return to satisfy type-checkers; unreachable because of raised exceptions.
    return {}
