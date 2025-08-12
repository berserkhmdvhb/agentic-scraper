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

from typing import Any
from urllib.parse import quote_plus

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from agentic_scraper import __api_version__ as api_version
from agentic_scraper.backend.core.settings import get_settings

settings = get_settings()

# Plain HTTP Bearer (paste an access token)
bearer_scheme = {
    "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Paste your Auth0 access token (raw JWT, without the 'Bearer ' prefix).",
    }
}

# OAuth2 Authorization Code (with PKCE) for Auth0 — lets users log in via Swagger UI
audience = getattr(settings, "auth0_api_audience", None)
aud_query = f"?audience={quote_plus(audience)}" if audience else ""
authorization_url = f"https://{settings.auth0_domain}/authorize{aud_query}"

oauth2_scheme = {
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
        app (FastAPI): The FastAPI app instance whose schema is being modified.

    Returns:
        dict[str, Any]: The customized OpenAPI schema.
    """
    if app.openapi_schema:
        return app.openapi_schema

    # Generate the base OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Customize metadata fields
    openapi_schema["info"]["title"] = "Agentic Scraper API"
    openapi_schema["info"]["description"] = "LLM-powered web scraper"
    openapi_schema["info"]["version"] = app.version
    openapi_schema["info"]["termsOfService"] = "https://example.com/terms"
    openapi_schema["info"]["contact"] = {
        "name": "API Support",
        "url": "https://example.com/support",
        "email": "support@example.com",
    }
    openapi_schema["info"]["license"] = {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    }

    # Security schemes
    components = openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})
    components.update(bearer_scheme)
    components.update(oauth2_scheme)

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
