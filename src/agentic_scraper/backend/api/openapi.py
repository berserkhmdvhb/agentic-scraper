"""
Custom OpenAPI schema generator for Agentic Scraper.

This module modifies FastAPI's default OpenAPI schema to:
- Embed a JWT Bearer authentication scheme.
- Add an OAuth2 (authorization code with PKCE) flow for Auth0 so users can log in from Swagger.
- Customize metadata (title, description, contact, license).
- Optionally set the `servers` entry to the deployed API base.
- Globally apply the security schemes to all endpoints.

Used at startup via the main app file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote_plus

from fastapi.openapi.utils import get_openapi

from agentic_scraper.backend.core.settings import get_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

# Plain HTTP Bearer (paste an access token)
BEARER_SCHEME: dict[str, dict[str, Any]] = {
    "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Paste your Auth0 access token (raw JWT, without the 'Bearer ' prefix).",
    }
}


def _oauth2_scheme() -> dict[str, Any]:
    """Build OAuth2 (Auth Code + PKCE) scheme from current settings."""
    settings = get_settings()
    audience = getattr(settings, "auth0_api_audience", None)
    aud_query = f"?audience={quote_plus(audience)}" if audience else ""
    authorization_url = f"https://{settings.auth0_domain}/authorize{aud_query}"
    return {
        "OAuth2Auth": {
            "type": "oauth2",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": authorization_url,
                    "tokenUrl": f"https://{settings.auth0_domain}/oauth/token",
                    "scopes": {
                        "openid": "OpenID Connect",
                        "profile": "Basic profile",
                        "email": "Email address",
                        "read:user_profile": "Read user profile",
                        "create:openai_credentials": "Manage OpenAI credentials",
                        "create:scrapes": "Create scrapes",
                        "read:scrapes": "Read scrapes",
                        "cancel:scrapes": "Cancel scrapes",
                    },
                }
            },
            "description": (
                "Authenticate with Auth0 (Authorization Code with PKCE). "
                "Requires your Auth0 app to allow callback: "
                "`/docs/oauth2-redirect` on this domain."
            ),
        }
    }


def _api_server_url() -> str | None:
    """Best-effort absolute API base for Swagger 'servers'."""
    settings = get_settings()
    base = (settings.backend_domain or "").rstrip("/")
    if not base:
        return None
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    return base


def custom_openapi(app: FastAPI) -> dict[str, Any]:
    """
    Customize the FastAPI OpenAPI schema to include Bearer & OAuth2 auth and extra metadata.

    Args:
        app: The FastAPI app instance whose schema is being modified.

    Returns:
        The customized OpenAPI schema.
    """
    if app.openapi_schema:
        return app.openapi_schema

    # Generate the base OpenAPI schema
    openapi_schema: dict[str, Any] = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Customize metadata fields
    info = openapi_schema.setdefault("info", {})
    info["title"] = "Agentic Scraper API"
    info["description"] = "LLM-powered web scraper"
    info["version"] = app.version
    info["termsOfService"] = "https://example.com/terms"
    info["contact"] = {
        "name": "API Support",
        "url": "https://example.com/support",
        "email": "support@example.com",
    }
    info["license"] = {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    }

    # Security schemes
    components = openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})
    components.update(BEARER_SCHEME)
    components.update(_oauth2_scheme())

    # Point Swagger at the deployed API base (if configured)
    server_url = _api_server_url()
    if server_url:
        openapi_schema["servers"] = [{"url": server_url}]

    # Apply security to all operations (allow either OAuth2 or pasted Bearer)
    for path_item in openapi_schema.get("paths", {}).values():
        for method in path_item.values():
            if isinstance(method, dict) and "security" not in method:
                method["security"] = [{"OAuth2Auth": []}, {"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema
