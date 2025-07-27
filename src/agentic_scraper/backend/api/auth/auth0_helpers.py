import logging
from functools import lru_cache
from typing import Any, cast

import httpx
from fastapi import HTTPException
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_FETCHING_JWKS,
    MSG_ERROR_INVALID_JWT_HEADER,
    MSG_ERROR_JWT_EXPIRED,
    MSG_ERROR_JWT_UNEXPECTED,
    MSG_ERROR_JWT_VERIFICATION,
    MSG_ERROR_NO_RSA_KEY,
    MSG_INFO_DECODING_JWT,
    MSG_INFO_FETCHING_JWKS,
    MSG_INFO_JWKS_FETCHED,
)
from agentic_scraper.backend.core.settings import get_settings

# Initialize logger
logger = logging.getLogger(__name__)

settings = get_settings()

def raise_http_exception(status_code: int, detail: str, error: Exception) -> None:
    """Helper function to raise an HTTP exception with detailed logging."""
    logger.exception(detail)  # Log the exception details
    raise HTTPException(status_code=status_code, detail=detail) from error
@lru_cache
def get_jwks() -> list[dict[str, Any]]:
    """
    Fetch and cache the JSON Web Key Set (JWKS) from Auth0.

    This set contains the public RSA keys used to verify JWT signatures.

    Returns:
        list[dict[str, Any]]: A list of public keys in JWKS format.

    Raises:
        HTTPException: If the JWKS endpoint cannot be reached or returns an error.
    """
    url = f"{settings.auth0_issuer}/.well-known/jwks.json"
    try:
        logger.info(MSG_INFO_FETCHING_JWKS.format(url=url))
        response = httpx.get(url)
        response.raise_for_status()
        jwks = response.json().get("keys", [])
        logger.info(MSG_INFO_JWKS_FETCHED.format(num_keys=len(jwks)))
        return cast("list[dict[str, Any]]", jwks)
    except httpx.HTTPError as e:
        raise_http_exception(503, MSG_ERROR_FETCHING_JWKS.format(error=str(e)), e)

    return []
def verify_jwt(token: str) -> dict[str, Any]:
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
                401,
                MSG_ERROR_INVALID_JWT_HEADER,
                ValueError("Invalid JWT header"))

        # Fetch the JWKS (JSON Web Key Set)
        jwks = get_jwks()

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
                ValueError("No matching RSA key"))

        # Define the JWT decode options
        options = {"verify_exp": True}

        # Decode the JWT and verify its signature, expiration, and claims
        logger.info(MSG_INFO_DECODING_JWT)
        return cast(
            "dict[str, Any]",
            jwt.decode(
                token,
                rsa_key,
                options=options,
                algorithms=settings.auth0_algorithm,
                audience=settings.auth0_audience,
                issuer=settings.auth0_issuer
            ),
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
