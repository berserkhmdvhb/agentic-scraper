"""
Custom OpenAPI schema generator for Agentic Scraper.

This module modifies FastAPI's default OpenAPI schema to:
- Embed a JWT Bearer authentication scheme.
- Customize metadata (title, description, contact, license).
- Globally apply the security scheme to all endpoints.

Used at startup via the main app file.
"""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

# Define the JWT Bearer authentication scheme
security_scheme = {
    "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Paste your Auth0 access token here to authorize",
    }
}


def custom_openapi(app: FastAPI) -> dict[str, Any]:
    """
    Customize the FastAPI OpenAPI schema to include Bearer auth and extra metadata.

    This modifies the auto-generated OpenAPI docs to:
    - Add global JWT bearer security scheme.
    - Apply the scheme to all routes.
    - Set detailed metadata such as contact and license.

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

    # Add the BearerAuth security scheme globally
    openapi_schema["components"]["securitySchemes"] = security_scheme
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema
