from __future__ import annotations

import base64
import importlib
import json
import logging
import os
import time
from collections.abc import AsyncGenerator, Generator, Callable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
from _pytest.logging import LogCaptureFixture
from _pytest.monkeypatch import MonkeyPatch
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt
from pydantic_settings import SettingsConfigDict

from agentic_scraper.backend.core import settings as settings_module
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

__all__ = [
    "clear_agentic_env",
    "disable_env_file",
    "reset_settings_cache",
    "reload_settings",
    "set_env_var",
    "log_stream",
    "debug_logger",
    "mock_env",
    "settings",
    "settings_factory",
    "no_network",
    "caplog_debug",
    "test_client",
    "api_base",
    "jwks_keypair",
    "jwks_mock",
    "make_jwt",
    "auth_header",
    "authorized_client_jwt",
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
]

TEST_FERNET_KEY = "A"*43 + "="

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
    defaults = {
        # Runtime / OpenAI (use project defaults to avoid drift)
        "OPENAI_API_KEY": "test-key",
        "ENV": DEFAULT_ENV,                    # e.g., "DEV"
        "OPENAI_MODEL": DEFAULT_OPENAI_MODEL,  # e.g., "gpt-4o" if that's your default

        # Auth0
        "AUTH0_ALGORITHMS": json.dumps([DEFAULT_AUTH0_ALGORITHM]),
        "AUTH0_DOMAIN": "dev-xxxxxx.us.auth0.com",
        "AUTH0_ISSUER": "https://dev-xxxxxx.us.auth0.com/",   # issuer needs trailing slash
        "AUTH0_CLIENT_ID": "your-client-id",
        "AUTH0_CLIENT_SECRET": "your-client-secret",
        "AUTH0_API_AUDIENCE": "https://api-agenticscraper.onrender.com",  # no trailing slash required
        "AUTH0_REDIRECT_URI": "https://api-agenticscraper.onrender.com/api/v1/auth/callback",

        # Domains
        "BACKEND_DOMAIN": "https://api-agenticscraper.onrender.com",
        "FRONTEND_DOMAIN": "https://agenticscraper.onrender.com",

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


@pytest.fixture(autouse=True)
def disable_env_file(monkeypatch: MonkeyPatch) -> None:
    """Patch Settings to disable .env file loading (avoids pydantic warning)."""
    class ConfiglessSettings(settings_module.Settings):
        # pydantic-settings v2 style
        model_config = SettingsConfigDict(env_file=None)

    monkeypatch.setattr(settings_module, "Settings", ConfiglessSettings)


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
def settings(mock_env: None, reset_settings_cache: Any) -> settings_module.Settings:
    # Use model_validate to bypass env file loading entirely
    return settings_module.Settings.model_validate({})


@pytest.fixture
def settings_factory() -> Callable[..., settings_module.Settings]:
    def _make(**overrides: Any) -> settings_module.Settings:
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
    import socket

    class NoNetSocket(socket.socket):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("Network disabled in tests")

    monkeypatch.setattr(socket, "socket", NoNetSocket)

    
# --------------------------------------------------------------------------- #
# FastAPI client
# --------------------------------------------------------------------------- #

@pytest.fixture
async def test_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    ASGI-aware HTTPX client bound to the FastAPI app.
    Uses app lifespan() and avoids mypy complaints by using ASGITransport.
    """
    from httpx import ASGITransport
    from agentic_scraper.backend.api.main import app

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def api_base() -> str:
    """Versioned API base path, e.g. '/api/v1'."""
    from agentic_scraper import __api_version__ as api_version
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
    from agentic_scraper.backend.api.auth import auth0_helpers as ah

    async def _fake_get_jwks() -> list[dict[str, str]]:
        return [jwks_keypair.public_jwk]

    monkeypatch.setattr(ah.jwks_cache_instance, "get_jwks", _fake_get_jwks, raising=True)


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
        scope: str | None = None,
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
            claims["scope"] = scope
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
    jwks_mock: None,
    make_jwt: Callable[..., str],
) -> Callable[[str | None], httpx.AsyncClient]:
    """
    Returns an HTTPX client with Authorization header set using a minted JWT.
    Call: client = authorized_client_jwt("read:user_profile")
    """
    def _with_scope(scope: str | None = None) -> httpx.AsyncClient:
        token: str = make_jwt(scope=scope) if scope is not None else make_jwt()
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        return test_client

    return _with_scope


# --------------------------------------------------------------------------- #
# user_store
# --------------------------------------------------------------------------- #




@pytest.fixture
def user_store_mod(monkeypatch: MonkeyPatch, tmp_path: Path) -> ModuleType:
    import agentic_scraper.backend.api.stores.user_store as us

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
            raise ValueError("invalid ciphertext")
        return value.split("enc:", 1)[1]

    monkeypatch.setattr(user_store_mod, "encrypt", _enc, raising=True)
    monkeypatch.setattr(user_store_mod, "decrypt", _dec, raising=True)

