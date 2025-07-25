from functools import lru_cache
from typing import Any, cast

import httpx
from fastapi import HTTPException
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from agentic_scraper.backend.core.settings import get_settings

settings = get_settings()


@lru_cache
def get_jwks() -> list[dict[str, Any]]:
    url = f"https://{settings.auth0_domain}/.well-known/jwks.json"
    try:
        response = httpx.get(url)
        response.raise_for_status()
        # Cast the return value to the expected type
        return cast("list[dict[str, Any]]", response.json().get("keys", []))
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=503, detail=f"Failed to fetch JWKS from Auth0: {e!s}"
        ) from e


def verify_jwt(token: str) -> dict[str, Any]:
    try:
        unverified_header = jwt.get_unverified_header(token)
        jwks = get_jwks()
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
            raise HTTPException(status_code=401, detail="Unable to find matching RSA key")

        options = {"verify_exp": True}
        # Cast the return value to the expected type
        return cast(
            "dict[str, Any]",
            jwt.decode(
                token,
                rsa_key,
                options=options,
                algorithms=settings.auth0_algorithms,
                audience=settings.api_audience,
                issuer=f"https://{settings.auth0_domain}/",
            ),
        )

    except ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="Token has expired") from e
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"JWT error: {e!s}") from e
