from __future__ import annotations

from typing import Any, Set

import httpx
import pytest
from fastapi import FastAPI, status
from fastapi.routing import APIRoute

from agentic_scraper import __api_version__ as api_version
from agentic_scraper import __version__ as version
from agentic_scraper.backend.core import settings as settings_module


def _all_paths(app: FastAPI) -> Set[str]:
    # Only APIRoute has `.path`; filter accordingly for mypy.
    return {route.path for route in app.routes if isinstance(route, APIRoute)}


def _has_path_prefix(paths: Set[str], prefix: str) -> bool:
    return any(p.startswith(prefix) for p in paths)


def _vpath(suffix: str) -> str:
    return f"/api/{api_version}/{suffix.lstrip('/')}"


@pytest.mark.asyncio
async def test_health_endpoint_ok_returns_version(
    test_client: httpx.AsyncClient,
) -> None:
    res = await test_client.get("/health")
    assert res.status_code == status.HTTP_200_OK
    data: dict[str, Any] = res.json()
    assert data == {"status": "ok", "version": version}


@pytest.mark.asyncio
async def test_root_endpoint_returns_links_and_version(
    test_client: httpx.AsyncClient,
) -> None:
    res = await test_client.get("/")
    assert res.status_code == status.HTTP_200_OK
    data: dict[str, Any] = res.json()
    assert data.get("message") == "Welcome to Agentic Scraper API"
    assert data.get("docs") == "/docs"
    assert data.get("version") == version


def test_versioned_routers_are_mounted(
    app_fast: FastAPI,
) -> None:
    paths = _all_paths(app_fast)
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
    test_client: httpx.AsyncClient,
    settings: settings_module.Settings,
) -> None:
    # Choose one allowed origin (fallback to localhost dev origin)
    origin = settings.frontend_domain or "http://localhost:8501"

    res = await test_client.get("/health", headers={"Origin": origin})
    assert res.status_code == status.HTTP_200_OK
    # For non-preflight requests, CORSMiddleware echoes the origin when allowed
    assert res.headers.get("access-control-allow-origin") == origin
