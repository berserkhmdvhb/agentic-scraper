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

# Initialize logger
logger = logging.getLogger(__name__)

settings = get_settings()

RETRY_LIMIT = 2  # Constant for retry limit


def raise_http_exception(status_code: int, detail: str, error: Exception) -> None:
    """Helper function to raise an HTTP exception with detailed logging."""
    logger.exception(detail)
    raise HTTPException(status_code=status_code, detail=detail) from error


class JWKSCache:
    def __init__(self) -> None:
        self.jwks_cache: list[dict[str, Any]] | None = None
        self.cache_timestamp: float | None = None
        self.cache_ttl = 3600  # Set TTL for cache (1 hour)

    async def get_jwks(self) -> list[dict[str, Any]]:
        """
        Fetch and cache the JSON Web Key Set (JWKS) from Auth0 during startup.
        """
        if self.jwks_cache is not None and self.cache_timestamp is not None:
            time_diff = time() - self.cache_timestamp
            if time_diff < self.cache_ttl:
                return self.jwks_cache  # Return cached JWKS if TTL has not expired

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
                    self.jwks_cache = jwks  # Cache the JWKS keys
                    self.cache_timestamp = time()
                    return cast("list[dict[str, Any]]", jwks)
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.exception(MSG_ERROR_FETCHING_JWKS)  # Log without redundant error details
                if attempt < RETRY_LIMIT:
                    logger.info(
                        MSG_INFO_RETRYING.format(attempt=attempt + 1, retry_limit=RETRY_LIMIT + 1)
                    )
                    await asyncio.sleep(randbelow(5) + 1)  # Random backoff for retry
                else:
                    raise_http_exception(503, MSG_ERROR_FETCHING_JWKS, e)
            except Exception as e:
                logger.exception(MSG_ERROR_FETCHING_JWKS)  # Log without redundant error details
                raise_http_exception(503, MSG_ERROR_FETCHING_JWKS, e)

            attempt += 1  # Increment the attempt counter

        return []  # Return empty list if fetching JWKS fails after retries


# Create an instance of JWKSCache
jwks_cache_instance = JWKSCache()


async def verify_jwt(token: str) -> dict[str, Any]:
    """
    Verify a JWT using Auth0's public keys.

    Args:
        token (str): The encoded JWT string to validate.

    Returns:
        dict[str, Any]: The decoded token payload if valid.

    Raises:
        HTTPException: If the token is expired, malformed, or unverifiable.
    """
    try:
        # Extract the unverified JWT header
        unverified_header = jwt.get_unverified_header(token)
        if not unverified_header:
            raise_http_exception(
                401, MSG_ERROR_INVALID_JWT_HEADER, ValueError("Invalid JWT header")
            )

        # Fetch the JWKS (JSON Web Key Set) which is preloaded during startup
        jwks = await jwks_cache_instance.get_jwks()

        # Find the RSA key corresponding to the JWT header
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

        # Define the JWT decode options
        options = {"verify_exp": True}

        # Decode the JWT and verify its signature, expiration, and claims
        logger.info(MSG_INFO_DECODING_JWT)
        decoded_token = jwt.decode(
            token,
            rsa_key,
            options=options,
            algorithms=settings.auth0_algorithms,
            audience=settings.auth0_api_audience,
            issuer=settings.auth0_issuer,
        )
        logger.info(MSG_INFO_DECODED_TOKEN.format(decoded_token=decoded_token))
        return cast(
            "dict[str, Any]",
            decoded_token,
        )

    except ExpiredSignatureError as e:
        raise_http_exception(401, MSG_ERROR_JWT_EXPIRED.format(error=str(e)), e)
    except JWTError as e:
        raise_http_exception(401, MSG_ERROR_JWT_VERIFICATION.format(error=str(e)), e)
    except ValueError as e:
        # Handle specific ValueError exception
        raise_http_exception(401, MSG_ERROR_JWT_UNEXPECTED.format(error=str(e)), e)
    except TypeError as e:
        # Handle specific TypeError exception
        raise_http_exception(401, MSG_ERROR_JWT_UNEXPECTED.format(error=str(e)), e)

    return {}  # Add a default return to silence mypy (not reached if exception is raised)
