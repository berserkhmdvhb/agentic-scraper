from __future__ import annotations

from typing import Any, Callable, Dict
from urllib.parse import quote_plus

from fastapi import FastAPI

from agentic_scraper.backend.core.settings import get_settings
from agentic_scraper.backend.api.openapi import custom_openapi
from agentic_scraper.backend.core import settings as settings_module
from agentic_scraper import __version__ as version


def _make_app() -> FastAPI:
    app = FastAPI(title="Test App", version=version, description="desc")

    @app.get("/ping")
    def ping() -> Dict[str, str]:
        return {"ok": "pong"}

    return app


def _schema_for(app: FastAPI) -> dict[str, Any]:
    return custom_openapi(app)


def test_security_schemes_and_global_application(
    settings: settings_module.Settings,  # ensures mock_env baseline is set
) -> None:
    app = _make_app()
    schema = _schema_for(app)

    comps = schema["components"]["securitySchemes"]
    assert "BearerAuth" in comps
    assert "OAuth2Auth" in comps

    get_op = schema["paths"]["/ping"]["get"]
    assert get_op["security"] == [{"OAuth2Auth": []}, {"BearerAuth": []}]

def test_servers_uses_backend_domain_when_set(
    settings: settings_module.Settings,
    reload_settings: Callable[[dict[str, str]], None],
) -> None:
    reload_settings({"BACKEND_DOMAIN": "api.example.com"})
    app = _make_app()
    schema = _schema_for(app)
    assert schema.get("servers") == [{"url": "https://api.example.com"}]

    # Even if a scheme is provided, settings normalization yields a host,
    # and OpenAPI generation emits HTTPS.
    reload_settings({"BACKEND_DOMAIN": "http://api.example.com"})
    app2 = _make_app()
    schema2 = _schema_for(app2)
    assert schema2.get("servers") == [{"url": "https://api.example.com"}]


def test_oauth_authorization_url_includes_audience_when_present(
    settings: settings_module.Settings,
    reload_settings: Callable[[dict[str, str]], None],
) -> None:
    reload_settings({"AUTH0_API_AUDIENCE": "https://api.example.com/space here"})
    app = _make_app()
    schema = _schema_for(app)

    # Fetch the *effective* audience from Settings after reload (accounts for normalization)
    effective_aud = get_settings().auth0_api_audience
    expected_param = f"audience={quote_plus(effective_aud)}"

    auth_url: str = schema["components"]["securitySchemes"]["OAuth2Auth"]["flows"][
        "authorizationCode"
    ]["authorizationUrl"]

    assert auth_url.startswith("https://test.auth0.com/authorize")
    assert expected_param in auth_url


def test_custom_openapi_caches_schema(
    settings: settings_module.Settings,
) -> None:
    app = _make_app()
    s1 = _schema_for(app)
    s2 = _schema_for(app)
    # Same object instance after first generation
    assert s1 is s2
