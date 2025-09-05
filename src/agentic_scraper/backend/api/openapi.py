"""
Custom OpenAPI schema generator for Agentic Scraper.

Endpoints / Dependencies:
- `custom_openapi`: Builds a modified OpenAPI schema for the FastAPI app.

Auth:
- Embeds both JWT Bearer (paste token) and OAuth2 (Auth Code + PKCE) schemes.
- OAuth2 integrates with Auth0 to allow Swagger UI login.

Response Models:
- None directly; this module only modifies schema metadata and security sections.

Usage:
    from fastapi import FastAPI
    from agentic_scraper.backend.api.openapi import custom_openapi

    app = FastAPI()
    app.openapi = lambda: custom_openapi(app)

Notes:
- Includes metadata (title, description, contact, license).
- Adds a global `servers` entry if `backend_domain` is configured.
- Security schemes are applied globally to operations that don't declare one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote_plus

from fastapi.openapi.utils import get_openapi

from agentic_scraper.backend.api.models import SCOPE_DESCRIPTIONS, RequiredScopes
from agentic_scraper.backend.core.settings import get_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

__all__ = ["custom_openapi"]

# Plain HTTP Bearer scheme (JWT tokens pasted manually into Swagger UI).
BEARER_SCHEME: dict[str, dict[str, Any]] = {
    "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Paste your Auth0 access token (raw JWT, without the 'Bearer ' prefix).",
    }
}


def _oauth2_scheme() -> dict[str, Any]:
    """
    Build OAuth2 (Authorization Code + PKCE) security scheme from current settings.

    Scope keys are sourced from `RequiredScopes`; descriptions come from
    `SCOPE_DESCRIPTIONS`. If a new scope lacks a description, a simple
    title-cased fallback is used to keep OpenAPI generation robust.

    Returns:
        dict[str, Any]: OAuth2 security scheme definition for OpenAPI.

    Notes:
        - Authorization URL is constructed with an optional `audience` query param
          when `AUTH0_API_AUDIENCE` is configured.
        - Swagger UI expects the callback path `/docs/oauth2-redirect`.
    """
    settings = get_settings()
    audience = getattr(settings, "auth0_api_audience", None)
    aud_query = f"?audience={quote_plus(audience)}" if audience else ""
    authorization_url = f"https://{settings.auth0_domain}/authorize{aud_query}"

    # Build scope map from enum, using a human-friendly fallback where needed.
    scopes = {
        scope.value: SCOPE_DESCRIPTIONS.get(
            scope, scope.value.split(":")[-1].replace("_", " ").title()
        )
        for scope in RequiredScopes
    }

    return {
        "OAuth2Auth": {
            "type": "oauth2",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": authorization_url,
                    "tokenUrl": f"https://{settings.auth0_domain}/oauth/token",
                    "scopes": {
                        # OIDC base scopes
                        "openid": "OpenID Connect",
                        "profile": "Basic profile",
                        "email": "Email address",
                        # Project scopes from a single source of truth
                        **scopes,
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
    """
    Build a best-effort absolute API base URL for Swagger `servers`.

    Returns:
        str | None: Normalized API base URL, or `None` if not configured.

    Notes:
        - Respects `settings.backend_domain`; adds scheme if missing and strips
          trailing slashes.
    """
    settings = get_settings()
    base = (settings.backend_domain or "").rstrip("/")
    if not base:
        return None
    if not base.startswith(("http://", "https://")):
        base = "https://" + base  # Default to https if scheme omitted.
    return base


def custom_openapi(app: FastAPI) -> dict[str, Any]:
    """
    Customize the FastAPI OpenAPI schema with authentication and metadata.

    Args:
        app (FastAPI): The FastAPI app instance whose schema is being modified.

    Returns:
        dict[str, Any]: The customized OpenAPI schema.

    Notes:
        - Caches the generated schema in `app.openapi_schema` to avoid recomputation.
        - Applies both OAuth2 and Bearer security globally to operations that
          don't already specify a `security` section.
    """
    if app.openapi_schema:
        return app.openapi_schema

    # Generate the base OpenAPI schema (introspects routes on the app).
    openapi_schema: dict[str, Any] = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Customize metadata fields.
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

    # Security schemes.
    components = openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})
    components.update(BEARER_SCHEME)
    components.update(_oauth2_scheme())

    # Point Swagger at the deployed API base (if configured).
    server_url = _api_server_url()
    if server_url:
        openapi_schema["servers"] = [{"url": server_url}]

    # Apply security to all operations (allow either OAuth2 or pasted Bearer).
    for path_item in openapi_schema.get("paths", {}).values():
        for method in path_item.values():
            # Only mutate genuine operation dicts; skip $ref or non-dict entries.
            if isinstance(method, dict) and "security" not in method:
                method["security"] = [{"OAuth2Auth": []}, {"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema
