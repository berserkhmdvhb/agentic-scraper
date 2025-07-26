from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

# Define the security scheme
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
    Customizes the OpenAPI schema to include JWT Bearer authentication.

    Args:
        app (FastAPI): The FastAPI app instance whose schema is being modified.

    Returns:
        dict: The customized OpenAPI schema with security definitions.
    """
    if app.openapi_schema:
        return app.openapi_schema

    # Generate the default OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Customize the info section
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

    # Add security scheme to OpenAPI schema
    openapi_schema["components"]["securitySchemes"] = security_scheme

    # Apply security scheme to each path operation
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"BearerAuth": []}]  # Apply security globally

    # Cache the customized OpenAPI schema in the app
    app.openapi_schema = openapi_schema
    return app.openapi_schema
