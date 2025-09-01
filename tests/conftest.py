from __future__ import annotations

import base64
import importlib
import json
import logging
import os
import socket
import time
from collections.abc import AsyncGenerator, Callable, Generator, Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, TypeAlias, cast

import httpx
import pytest
import pytest_asyncio
import streamlit as st
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport
from jose import jwt
from pydantic_settings import SettingsConfigDict

from agentic_scraper import __api_version__ as api_version
from agentic_scraper.backend.config.constants import (
    DEFAULT_AUTH0_ALGORITHM,
    DEFAULT_DEBUG_MODE,
    DEFAULT_DUMP_LLM_JSON_DIR,
    DEFAULT_ENV,
    DEFAULT_FETCH_CONCURRENCY,
    DEFAULT_LLM_CONCURRENCY,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_SCHEMA_RETRIES,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_LOG_BACKUP_COUNT,
    DEFAULT_LOG_DIR,
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_MAX_BYTES,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_BACKOFF_MAX,
    DEFAULT_RETRY_BACKOFF_MIN,
    DEFAULT_SCREENSHOT_DIR,
    DEFAULT_SCREENSHOT_ENABLED,
    DEFAULT_VERBOSE,
)
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_INVALID_CIPHERTEXT,
    MSG_ERROR_NO_NETWORK,
)
from agentic_scraper.backend.core import settings as settings_module

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from fastapi import FastAPI
    from streamlit.testing.v1 import AppTest as _AppTest

    AppTest: _AppTest | None
else:
    try:
        # Available in Streamlit 1.31+; safe to import conditionally.
        from streamlit.testing.v1 import AppTest  # runtime import
    except (ImportError, ModuleNotFoundError):
        AppTest = None

__all__ = [
    "api_base",
    "auth_header",
    "authorized_client_jwt",
    "caplog_debug",
    "clear_agentic_env",
    "debug_logger",
    "disable_env_file",
    "jwks_keypair",
    "jwks_mock",
    "log_stream",
    "make_jwt",
    "mock_env",
    "no_network",
    "reload_settings",
    "reset_settings_cache",
    "set_env_var",
    "settings",
    "settings_factory",
    "test_client",
]

# --------------------------------------------------------------------------- #
# Global test helpers / constants
# --------------------------------------------------------------------------- #

AGENTIC_ENV_VARS = [
    "OPENAI_API_KEY",
    "ENV",
    "OPENAI_MODEL",
    "DEBUG",
    "VERBOSE",
    "LOG_LEVEL",
    "LOG_FORMAT",
    "LOG_MAX_BYTES",
    "LOG_BACKUP_COUNT",
    "LOG_DIR",
    "SCREENSHOT_ENABLED",
    "SCREENSHOT_DIR",
    "MAX_CONCURRENT_REQUESTS",
    "LLM_MAX_TOKENS",
    "LLM_TEMPERATURE",
    "REQUEST_TIMEOUT",
    "FETCH_CONCURRENCY",
    "LLM_CONCURRENCY",
    "RETRY_ATTEMPTS",
    "RETRY_BACKOFF_MIN",
    "RETRY_BACKOFF_MAX",
    "DUMP_LLM_JSON_DIR",
    "LLM_SCHEMA_RETRIES",
    "AUTH0_DOMAIN",
    "AUTH0_ISSUER",
    "AUTH0_CLIENT_ID",
    "AUTH0_CLIENT_SECRET",
    "AUTH0_API_AUDIENCE",
    "AUTH0_ALGORITHMS",
    "ENCRYPTION_SECRET",
    "BACKEND_DOMAIN",
    "FRONTEND_DOMAIN",
    "AUTH0_REDIRECT_URI",
    "SKIP_JWKS_PRELOAD",
]

TEST_FERNET_KEY = "A" * 43 + "="


Store: TypeAlias = dict[str, dict[str, Any]]


@dataclass(frozen=True)
class JWKSKeypair:
    private_pem: str
    public_jwk: dict[str, str]
    kid: str


# --------------------------------------------------------------------------- #
# Ensure baseline env exists *before* test collection/imports
# (prevents import-time get_settings() from failing in modules like utils/crypto)
# --------------------------------------------------------------------------- #


def pytest_sessionstart(session: pytest.Session) -> None:
    """Seed minimal env so modules that call get_settings() at import time don't explode."""
    _ = session  # silence unused-argument warning (Ruff ARG001)
    defaults = {
        # Runtime / OpenAI (use project defaults to avoid drift)
        "OPENAI_API_KEY": "test-key",
        "ENV": DEFAULT_ENV,  # e.g., "DEV"
        "OPENAI_MODEL": DEFAULT_OPENAI_MODEL,  # e.g., "gpt-4o" if that's your default
        # Auth0
        "AUTH0_ALGORITHMS": json.dumps([DEFAULT_AUTH0_ALGORITHM]),
        "AUTH0_DOMAIN": "dev-xxxxxx.us.auth0.com",
        # issuer needs trailing slash
        "AUTH0_ISSUER": "https://dev-xxxxxx.us.auth0.com/",
        "AUTH0_CLIENT_ID": "your-client-id",
        "AUTH0_CLIENT_SECRET": "your-client-secret",
        "AUTH0_API_AUDIENCE": "https://api.example.com",
        "AUTH0_REDIRECT_URI": "https://api.example.com/api/{api_version}/auth/callback",
        # Domains
        "BACKEND_DOMAIN": "https://api.example.com",
        "FRONTEND_DOMAIN": "https://app.example.com",
        # Tests should never hit network for JWKS preload
        "SKIP_JWKS_PRELOAD": "true",
        # Crypto
        # Valid Fernet key: 32 url-safe base64-encoded bytes (44 chars)
        "ENCRYPTION_SECRET": TEST_FERNET_KEY,
    }
    for k, v in defaults.items():
        os.environ.setdefault(k, v)


def _b64url_uint(n: int) -> str:
    """Convert integer to base64url without padding."""
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


# --------------------------------------------------------------------------- #
# Settings isolation
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def clear_agentic_env(monkeypatch: MonkeyPatch) -> None:
    for var in AGENTIC_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True, scope="session")
def disable_env_file() -> Generator[None, None, None]:
    """Disable .env loading for the whole test session
    without using the function-scoped monkeypatch."""
    mp = pytest.MonkeyPatch()

    class ConfiglessSettings(settings_module.Settings):
        # pydantic-settings v2 style: ensure no .env files are read
        model_config = SettingsConfigDict(env_file=None)

    mp.setattr(settings_module, "Settings", ConfiglessSettings)
    try:
        yield
    finally:
        mp.undo()


@pytest.fixture
def mock_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ENV", DEFAULT_ENV)
    monkeypatch.setenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    # Booleans in envs are typically lowercase strings
    monkeypatch.setenv("DEBUG", str(DEFAULT_DEBUG_MODE).lower())
    monkeypatch.setenv("VERBOSE", str(DEFAULT_VERBOSE).lower())
    monkeypatch.setenv("LOG_LEVEL", DEFAULT_LOG_LEVEL)
    monkeypatch.setenv("LOG_FORMAT", DEFAULT_LOG_FORMAT)
    monkeypatch.setenv("LOG_MAX_BYTES", str(DEFAULT_LOG_MAX_BYTES))
    monkeypatch.setenv("LOG_BACKUP_COUNT", str(DEFAULT_LOG_BACKUP_COUNT))
    monkeypatch.setenv("LOG_DIR", DEFAULT_LOG_DIR)
    monkeypatch.setenv("SCREENSHOT_ENABLED", str(DEFAULT_SCREENSHOT_ENABLED).lower())
    monkeypatch.setenv("SCREENSHOT_DIR", DEFAULT_SCREENSHOT_DIR)
    monkeypatch.setenv("MAX_CONCURRENT_REQUESTS", str(DEFAULT_MAX_CONCURRENT_REQUESTS))
    monkeypatch.setenv("LLM_MAX_TOKENS", str(DEFAULT_LLM_MAX_TOKENS))
    monkeypatch.setenv("LLM_TEMPERATURE", str(DEFAULT_LLM_TEMPERATURE))
    monkeypatch.setenv("REQUEST_TIMEOUT", str(DEFAULT_REQUEST_TIMEOUT))
    monkeypatch.setenv("FETCH_CONCURRENCY", str(DEFAULT_FETCH_CONCURRENCY))
    monkeypatch.setenv("LLM_CONCURRENCY", str(DEFAULT_LLM_CONCURRENCY))
    monkeypatch.setenv("RETRY_ATTEMPTS", str(DEFAULT_RETRY_ATTEMPTS))
    monkeypatch.setenv("RETRY_BACKOFF_MIN", str(DEFAULT_RETRY_BACKOFF_MIN))
    monkeypatch.setenv("RETRY_BACKOFF_MAX", str(DEFAULT_RETRY_BACKOFF_MAX))
    monkeypatch.setenv("DUMP_LLM_JSON_DIR", DEFAULT_DUMP_LLM_JSON_DIR)
    monkeypatch.setenv("LLM_SCHEMA_RETRIES", str(DEFAULT_LLM_SCHEMA_RETRIES))
    monkeypatch.setenv("AUTH0_DOMAIN", "test.auth0.com")
    monkeypatch.setenv("AUTH0_ISSUER", "https://test.auth0.com/")
    monkeypatch.setenv("AUTH0_CLIENT_ID", "client-id")
    monkeypatch.setenv("AUTH0_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("AUTH0_API_AUDIENCE", "https://api.example.com")
    # JSON list of algorithms
    monkeypatch.setenv("AUTH0_ALGORITHMS", json.dumps([DEFAULT_AUTH0_ALGORITHM]))
    monkeypatch.setenv("ENCRYPTION_SECRET", TEST_FERNET_KEY)
    monkeypatch.setenv("BACKEND_DOMAIN", "http://api.example.com")
    monkeypatch.setenv("FRONTEND_DOMAIN", "http://app.example.com")
    monkeypatch.setenv("AUTH0_REDIRECT_URI", "http://app.example.com/callback")
    monkeypatch.setenv("SKIP_JWKS_PRELOAD", "true")


# --- alias fixtures for underscored variants used by tests ------------------- #
@pytest.fixture
def _mock_env(mock_env: None) -> None:
    """Alias to enforce execution order; depends on `mock_env`."""
    _ = mock_env  # consume to satisfy Ruff ARG001


@pytest.fixture
def _reset_settings_cache(reset_settings_cache: None) -> None:
    """Alias to enforce execution order; depends on `reset_settings_cache`."""
    _ = reset_settings_cache  # consume to satisfy Ruff ARG001


@pytest.fixture
def reset_settings_cache() -> Generator[None, None, None]:
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest.fixture
def reload_settings(monkeypatch: MonkeyPatch) -> Callable[[dict[str, str]], None]:
    def _reload(env_vars: dict[str, str]) -> None:
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        # Clear caches before and after reload to avoid stale instances
        settings_module.get_settings.cache_clear()
        importlib.reload(settings_module)

        class ConfiglessSettings(settings_module.Settings):
            model_config = SettingsConfigDict(env_file=None)

        monkeypatch.setattr(settings_module, "Settings", ConfiglessSettings)
        settings_module.get_settings.cache_clear()

    return _reload


@pytest.fixture
def set_env_var(monkeypatch: MonkeyPatch) -> Callable[[str, str], None]:
    return monkeypatch.setenv


@pytest.fixture
def settings(_mock_env: None, _reset_settings_cache: None) -> settings_module.Settings:
    # Use model_validate to bypass env file loading entirely
    return settings_module.Settings.model_validate({})


@pytest.fixture
def settings_factory() -> Callable[..., settings_module.Settings]:
    def _make(**overrides: object) -> settings_module.Settings:
        # Minimal base to satisfy validation; tests can override as needed
        base = {
            "AUTH0_DOMAIN": "test.auth0.com",
            "AUTH0_ISSUER": "https://test.auth0.com/",
            "AUTH0_CLIENT_ID": "client-id",
            "AUTH0_CLIENT_SECRET": "client-secret",
            "AUTH0_API_AUDIENCE": "https://api.example.com",
            "ENCRYPTION_SECRET": TEST_FERNET_KEY,
            "BACKEND_DOMAIN": "http://api.example.com",
            "FRONTEND_DOMAIN": "http://app.example.com",
            "AUTH0_REDIRECT_URI": "http://app.example.com/callback",
        }
        return settings_module.Settings.model_validate({**base, **overrides})

    return _make


# --------------------------------------------------------------------------- #
# Logging & misc
# --------------------------------------------------------------------------- #


@pytest.fixture
def log_stream() -> StringIO:
    return StringIO()


@pytest.fixture
def debug_logger(log_stream: StringIO) -> Generator[logging.Logger, None, None]:
    """Provide a clean logger that writes to an in-memory stream and restore after."""
    logger = logging.getLogger("agentic_scraper")
    prev_level = logger.level
    prev_handlers = logger.handlers[:]
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.handlers = [handler]
    try:
        yield logger
    finally:
        logger.setLevel(prev_level)
        logger.handlers = prev_handlers


@pytest.fixture
def caplog_debug(caplog: LogCaptureFixture) -> LogCaptureFixture:
    """Convenience fixture to set caplog level to DEBUG for tests asserting logs."""
    caplog.set_level(logging.DEBUG)
    return caplog


@pytest.fixture
def no_network(monkeypatch: MonkeyPatch) -> None:
    """Disable real network calls in tests that must remain offline."""

    class NoNetSocket(socket.socket):
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError(MSG_ERROR_NO_NETWORK)

    monkeypatch.setattr(socket, "socket", NoNetSocket)


# --------------------------------------------------------------------------- #
# FastAPI client
# --------------------------------------------------------------------------- #


@pytest.fixture
def app_fast(
    monkeypatch: MonkeyPatch,
    _mock_env: None,
    _jwks_mock: None,
) -> FastAPI:
    """
    Import the FastAPI app with slow side effects stubbed:
    - logger_setup.setup_logging -> no-op
    - auth0_helpers.jwks_cache_instance.get_jwks -> stubbed by jwks_mock
    """
    logger_setup = importlib.import_module("agentic_scraper.backend.core.logger_setup")
    monkeypatch.setattr(logger_setup, "setup_logging", lambda: None, raising=True)

    # Now import the app after patches are in place

    app_mod = importlib.import_module("agentic_scraper.backend.api.main")
    return cast("FastAPI", app_mod.app)


@pytest_asyncio.fixture
async def test_client(app_fast: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    ASGI-aware HTTPX client bound to the FastAPI app.
    Uses app lifespan() and avoids mypy complaints by using ASGITransport.
    """

    transport = ASGITransport(app=app_fast)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def api_base() -> str:
    """Versioned API base path, e.g. '/api/v1'."""
    return f"/api/{api_version}"


# --------------------------------------------------------------------------- #
# Auth fixtures (JWKS / JWT) using @dataclass
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def jwks_keypair() -> JWKSKeypair:
    """
    Generate an RSA keypair and corresponding JWK with a stable kid.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    public_numbers = key.public_key().public_numbers()
    n_b64 = _b64url_uint(public_numbers.n)
    e_b64 = _b64url_uint(public_numbers.e)

    kid = "test-key-id"
    public_jwk: dict[str, str] = {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "n": n_b64,
        "e": e_b64,
    }
    return JWKSKeypair(private_pem=private_pem, public_jwk=public_jwk, kid=kid)


@pytest.fixture
def jwks_mock(monkeypatch: MonkeyPatch, jwks_keypair: JWKSKeypair) -> None:
    """Monkeypatch JWKS fetch to return our in-memory JWK."""
    ah = importlib.import_module("agentic_scraper.backend.api.auth.auth0_helpers")

    async def _fake_get_jwks() -> list[dict[str, str]]:
        return [jwks_keypair.public_jwk]

    monkeypatch.setattr(ah.jwks_cache_instance, "get_jwks", _fake_get_jwks, raising=True)


@pytest.fixture
def _jwks_mock(jwks_mock: None) -> None:
    """Alias to enforce execution order; depends on `jwks_mock`."""
    _ = jwks_mock  # consume to satisfy Ruff ARG001


@pytest.fixture
def make_jwt(settings: settings_module.Settings, jwks_keypair: JWKSKeypair) -> Callable[..., str]:
    """
    Factory that returns a signed RS256 JWT matching Settings (iss, aud).
    Usage:
        token = make_jwt(sub="auth0|123", scope="read:user_profile")
    """

    def _issue(
        *,
        sub: str = "auth0|user123",
        scope: str | list[str] | None = None,
        expires_in: int = 3600,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": settings.auth0_issuer,
            "aud": settings.auth0_api_audience,
            "iat": now,
            "exp": now + expires_in,
            "sub": sub,
        }
        if scope is not None:
            # Accept both space-delimited string and list[str]
            claims["scope"] = " ".join(scope) if isinstance(scope, list) else scope
        if extra_claims:
            claims.update(extra_claims)

        headers = {"kid": jwks_keypair.kid, "alg": "RS256", "typ": "JWT"}
        token = jwt.encode(claims, jwks_keypair.private_pem, algorithm="RS256", headers=headers)
        # python-jose types encode() as Any; coerce to str for mypy
        return str(token)

    return _issue


@pytest.fixture
def auth_header(make_jwt: Callable[..., str]) -> dict[str, str]:
    token: str = make_jwt()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def authorized_client_jwt(
    test_client: httpx.AsyncClient,
    _jwks_mock: None,
    make_jwt: Callable[..., str],
) -> Callable[[str | None], httpx.AsyncClient]:
    """
    Returns an HTTPX client with Authorization header set using a minted JWT.
    Call: client = authorized_client_jwt("read:user_profile")
    """

    def _with_scope(scope: str | list[str] | None = None) -> httpx.AsyncClient:
        token: str = make_jwt(scope=scope) if scope is not None else make_jwt()
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        return test_client

    return _with_scope


# --------------------------------------------------------------------------- #
# user_store
# --------------------------------------------------------------------------- #


@pytest.fixture
def user_store_mod(monkeypatch: MonkeyPatch, tmp_path: Path) -> ModuleType:
    us = importlib.import_module("agentic_scraper.backend.api.stores.user_store")

    store_path: Path = tmp_path / "user_store.json"
    store_path.write_text("{}")
    monkeypatch.setattr(us, "USER_STORE", store_path, raising=True)
    us.USER_STORE.parent.mkdir(parents=True, exist_ok=True)
    return us


@pytest.fixture
def stub_crypto(monkeypatch: MonkeyPatch, user_store_mod: ModuleType) -> None:
    def _enc(value: str) -> str:
        return f"enc:{value}"

    def _dec(value: str) -> str:
        if not isinstance(value, str) or not value.startswith("enc:"):
            raise ValueError(MSG_ERROR_INVALID_CIPHERTEXT)
        return value.split("enc:", 1)[1]

    monkeypatch.setattr(user_store_mod, "encrypt", _enc, raising=True)
    monkeypatch.setattr(user_store_mod, "decrypt", _dec, raising=True)


@pytest.fixture
def patch_job_store(monkeypatch: MonkeyPatch) -> Callable[[ModuleType, Store | None], Store]:
    """
    Patch a module's get_job/update_job to use an in-memory store.

    Usage:
        store = patch_job_store(sh, {"queued": {"status": "queued"}})
        # sh.get_job("queued") -> {"status": "queued"}
        # sh.update_job("queued", status="running")
    """

    def _patch(module: ModuleType, initial: Store | None = None) -> Store:
        store: Store = dict(initial or {})

        def get_job(job_id: str) -> dict[str, Any] | None:
            return store.get(job_id)

        def update_job(job_id: str, **kwargs: object) -> dict[str, Any] | None:
            snap = store.get(job_id)
            if snap is None:
                return None
            snap.update(kwargs)
            return snap

        monkeypatch.setattr(module, "get_job", get_job, raising=True)
        monkeypatch.setattr(module, "update_job", update_job, raising=True)
        return store

    return _patch


@pytest.fixture(name="_settings")
def _settings_alias(
    settings: settings_module.Settings,
) -> settings_module.Settings:
    """Back-compat alias so tests using `_settings` use the canonical `settings`."""
    return settings


# --------------------------------------------------------------------------- #
# streamlit- frontend/
# --------------------------------------------------------------------------- #


@pytest.fixture
def st_session() -> Callable[[Mapping[str, Any] | None], None]:
    """
    Seed Streamlit's session_state in a controlled way.

    Usage:
        st_session({"jwt_token": "abc123", "some_flag": True})
    """

    def _seed(values: Mapping[str, Any] | None = None) -> None:
        # Ensure a clean slate for each test that calls this
        st.session_state.clear()
        if values:
            for k, v in values.items():
                st.session_state[k] = v

    return _seed


@pytest.fixture
def streamlit_app_test() -> Callable[[str], object]:
    """
    Run a Streamlit app file with the testing harness and return the AppTest instance.
    Skips tests gracefully if the harness isn't available.
    """
    if AppTest is None:
        pytest.skip("Streamlit testing harness is not available (streamlit.testing.v1).")

    def _run(app_path: str) -> object:
        return AppTest.from_file(app_path)

    return _run


class _MockRouter:
    """
    Simple router for httpx.MockTransport used in frontend tests.
    Match by METHOD + absolute URL. Allows json/text/static responses or custom handlers.
    """

    def __init__(self) -> None:
        self._routes: list[tuple[str, str, Callable[[httpx.Request], httpx.Response]]] = []

    def add_json(
        self,
        method: str,
        url: str,
        status: int = 200,
        json_data: object | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        def _handler(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(status, json=json_data, headers=dict(headers or {}))

        self._routes.append((method.upper(), url, _handler))

    def add_text(
        self,
        method: str,
        url: str,
        status: int = 200,
        text: str = "",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        def _handler(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(status, text=text, headers=dict(headers or {}))

        self._routes.append((method.upper(), url, _handler))

    def add_handler(
        self, method: str, url: str, handler: Callable[[httpx.Request], httpx.Response]
    ) -> None:
        self._routes.append((method.upper(), url, handler))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        method = request.method.upper()
        url = str(request.url)
        for meth, full_url, handler in self._routes:
            if meth == method and full_url == url:
                return handler(request)
        # Default: 404 for unmatched routes to surface mistakes in tests
        return httpx.Response(404, text=f"No mock route for {method} {url}")


@pytest.fixture
def httpx_backend_mock(monkeypatch: MonkeyPatch) -> Callable[[], _MockRouter]:
    """
    Patch httpx.AsyncClient to always use a MockTransport with a local router.
    Tests can register routes against absolute URLs.

    Usage:
        router = httpx_backend_mock()
        router.add_json("POST", "http://api.example.com/api/v1/scrape/start", 200, {"ok": True})
        # Now code that creates httpx.AsyncClient() internally will hit this mock.
    """
    router = _MockRouter()
    mock_transport = httpx.MockTransport(router)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(
            self,
            *,
            transport: httpx.AsyncBaseTransport | None = None,
            follow_redirects: bool | None = None,
        ) -> None:
            # Force our mock transport unless explicitly provided; allow follow_redirects
            super().__init__(
                transport=transport or mock_transport,
                follow_redirects=bool(follow_redirects) if follow_redirects is not None else False,
            )

    monkeypatch.setattr(httpx, "AsyncClient", PatchedAsyncClient, raising=True)

    def _get_router() -> _MockRouter:
        return router

    return _get_router
