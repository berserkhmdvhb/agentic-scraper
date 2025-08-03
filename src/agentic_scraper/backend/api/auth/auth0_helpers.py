"""
Utilities for verifying JWTs using Auth0's JWKS (JSON Web Key Set).

This module provides:
- A retryable JWKS fetcher with caching (JWKSCache).
- A secure JWT verification function (verify_jwt).
- A helper to raise HTTP exceptions with consistent logging.

Used by FastAPI dependencies to authenticate users via Auth0.
"""

import asyncio
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
    MSG_ERROR_FETCHING_JWKS,
    MSG_ERROR_INVALID_JWT_HEADER,
    MSG_ERROR_JWT_EXPIRED,
    MSG_ERROR_JWT_UNEXPECTED,
    MSG_ERROR_JWT_VERIFICATION,
    MSG_ERROR_NO_RSA_KEY,
    MSG_INFO_DECODED_TOKEN,
    MSG_INFO_DECODING_JWT,
    MSG_INFO_FETCHING_JWKS,
    MSG_INFO_JWKS_FETCHED,
    MSG_INFO_RETRYING,
)
from agentic_scraper.backend.core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

RETRY_LIMIT = 2  # Retry limit for JWKS fetch attempts


def raise_http_exception(status_code: int, detail: str, error: Exception) -> None:
    """
    Raise an HTTPException with detailed logging for debugging.

    Args:
        status_code (int): HTTP status code to return.
        detail (str): Error message to show in the response.
        error (Exception): Original exception to attach.

    Raises:
        HTTPException: Always raised, with the original exception attached.
    """
    logger.exception(detail)
    raise HTTPException(status_code=status_code, detail=detail) from error


class JWKSCache:
    """
    Caches and fetches JWKS (JSON Web Key Set) for Auth0 token verification.

    Fetches are retried on transient failures. Cached results are reused for 1 hour.
    """

    def __init__(self) -> None:
        self.jwks_cache: list[dict[str, Any]] | None = None
        self.cache_timestamp: float | None = None
        self.cache_ttl = 3600  # 1 hour TTL

    async def get_jwks(self) -> list[dict[str, Any]]:
        """
        Fetch and cache the JWKS (JSON Web Key Set) from Auth0.

        Returns:
            list[dict[str, Any]]: A list of key dictionaries for verifying JWTs.

        Raises:
            HTTPException: If JWKS fetching fails after all retry attempts.
        """
        if (
            self.jwks_cache
            and self.cache_timestamp
            and (time() - self.cache_timestamp < self.cache_ttl)
        ):
            return self.jwks_cache

        url = f"{settings.auth0_issuer}.well-known/jwks.json"
        logger.debug(MSG_DEBUG_CURRENT_ISSUER.format(issuer=url))

        attempt = 0
        while attempt <= RETRY_LIMIT:
            try:
                logger.info(MSG_INFO_FETCHING_JWKS.format(url=url))
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    jwks = response.json().get("keys", [])
                    logger.info(MSG_INFO_JWKS_FETCHED.format(num_keys=len(jwks)))
                    self.jwks_cache = jwks
                    self.cache_timestamp = time()
                    return cast("list[dict[str, Any]]", jwks)
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.exception(MSG_ERROR_FETCHING_JWKS)
                if attempt < RETRY_LIMIT:
                    logger.info(
                        MSG_INFO_RETRYING.format(attempt=attempt + 1, retry_limit=RETRY_LIMIT + 1)
                    )
                    await asyncio.sleep(randbelow(5) + 1)  # Random backoff
                else:
                    raise_http_exception(503, MSG_ERROR_FETCHING_JWKS, e)
            except Exception as e:
                logger.exception(MSG_ERROR_FETCHING_JWKS)
                raise_http_exception(503, MSG_ERROR_FETCHING_JWKS, e)

            attempt += 1

        return []  # Fallback to avoid crash (should not be reached)


# Shared instance of the JWKS cache
jwks_cache_instance = JWKSCache()


async def verify_jwt(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT using the JWKS from Auth0.

    Args:
        token (str): The JWT token string received from the client.

    Returns:
        dict[str, Any]: The decoded payload if the token is valid.

    Raises:
        HTTPException: If the JWT is expired, malformed, or unverifiable.
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
        if not unverified_header:
            raise_http_exception(
                401, MSG_ERROR_INVALID_JWT_HEADER, ValueError("Invalid JWT header")
            )

        jwks = await jwks_cache_instance.get_jwks()

        rsa_key = {}
        for key in jwks:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            raise_http_exception(
                401,
                MSG_ERROR_NO_RSA_KEY.format(kid=unverified_header["kid"]),
                ValueError("No matching RSA key"),
            )

        logger.info(MSG_INFO_DECODING_JWT)
        decoded_token = jwt.decode(
            token,
            rsa_key,
            options={"verify_exp": True},
            algorithms=settings.auth0_algorithms,
            audience=settings.auth0_api_audience,
            issuer=settings.auth0_issuer,
        )
        logger.info(MSG_INFO_DECODED_TOKEN.format(decoded_token=decoded_token))
        return cast("dict[str, Any]", decoded_token)

    except ExpiredSignatureError as e:
        raise_http_exception(401, MSG_ERROR_JWT_EXPIRED.format(error=str(e)), e)
    except JWTError as e:
        raise_http_exception(401, MSG_ERROR_JWT_VERIFICATION.format(error=str(e)), e)
    except (ValueError, TypeError) as e:
        raise_http_exception(401, MSG_ERROR_JWT_UNEXPECTED.format(error=str(e)), e)

    return {}
