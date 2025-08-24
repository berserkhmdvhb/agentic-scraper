from __future__ import annotations

from typing import Any
import importlib

import httpx
import pytest
from fastapi import FastAPI, status
from fastapi.routing import APIRoute
from httpx import ASGITransport

from agentic_scraper import __api_version__ as api_version
from agentic_scraper import __version__ as version
from agentic_scraper.backend.core import settings as settings_module


def _import_app_fast(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """
    Import the FastAPI app while stubbing slow or networked side effects:
    - logger_setup.setup_logging -> no-op
    - auth0_helpers.jwks_cache_instance.get_jwks -> fast async stub
    """
    # Patch logging bootstrap to avoid file I/O.
    logger_setup = importlib.import_module("agentic_scraper.backend.core.logger_setup")
    monkeypatch.setattr(logger_setup, "setup_logging", lambda: None, raising=True)

    # Patch JWKS preload to a fast no-op in case lifespan runs.
    auth0_helpers = importlib.import_module("agentic_scraper.backend.api.auth.auth0_helpers")

    async def _stub_jwks() -> list[dict[str, str]]:
        return []

    monkeypatch.setattr(auth0_helpers.jwks_cache_instance, "get_jwks", _stub_jwks, raising=True)

    # Now import the app.
    main = importlib.import_module("agentic_scraper.backend.api.main")
    app_obj: Any = getattr(main, "app")
    # Narrow the type safely for mypy
    assert isinstance(app_obj, FastAPI)
    return app_obj


@pytest.mark.asyncio
async def test_health_endpoint_ok_returns_version(
    monkeypatch: pytest.MonkeyPatch,
    settings: settings_module.Settings,
) -> None:
    app = _import_app_fast(monkeypatch)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        res = await client.get("/health")
        assert res.status_code == status.HTTP_200_OK
        data: dict[str, Any] = res.json()
        assert data == {"status": "ok", "version": version}


@pytest.mark.asyncio
async def test_root_endpoint_returns_links_and_version(
    monkeypatch: pytest.MonkeyPatch,
    settings: settings_module.Settings,
) -> None:
    app = _import_app_fast(monkeypatch)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        res = await client.get("/")
        assert res.status_code == status.HTTP_200_OK
        data: dict[str, Any] = res.json()
        assert data.get("message") == "Welcome to Agentic Scraper API"
        assert data.get("docs") == "/docs"
        assert data.get("version") == version


def _all_paths(app: FastAPI) -> set[str]:
    # Only APIRoute has `.path`; filter accordingly to satisfy mypy.
    return {route.path for route in app.routes if isinstance(route, APIRoute)}


def _has_path_prefix(paths: set[str], prefix: str) -> bool:
    return any(p.startswith(prefix) for p in paths)


def _vpath(suffix: str) -> str:
    return f"/api/{api_version}/{suffix.lstrip('/')}"


def test_versioned_routers_are_mounted(
    monkeypatch: pytest.MonkeyPatch,
    settings: settings_module.Settings,
) -> None:
    app = _import_app_fast(monkeypatch)

    paths = _all_paths(app)
    assert _has_path_prefix(paths, f"/api/{api_version}/")
    # Be flexible about actual router names while ensuring versioned mounts exist.
    assert any(
        _has_path_prefix(paths, prefix)
        for prefix in (
            _vpath("auth"),
            _vpath("user"),
            _vpath("users"),
            _vpath("scrape"),
            _vpath("scrapes"),
        )
    ), f"Expected a versioned router under /api/{api_version}; saw: {sorted(paths)}"


@pytest.mark.asyncio
async def test_cors_echoes_allowed_origin(
    monkeypatch: pytest.MonkeyPatch,
    settings: settings_module.Settings,
) -> None:
    app = _import_app_fast(monkeypatch)

    # Choose one allowed origin (fallback to localhost dev origin)
    origin = settings.frontend_domain or "http://localhost:8501"

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        res = await client.get("/health", headers={"Origin": origin})
        assert res.status_code == status.HTTP_200_OK
        # For non-preflight requests, CORSMiddleware echoes the origin when allowed
        assert res.headers.get("access-control-allow-origin") == origin
