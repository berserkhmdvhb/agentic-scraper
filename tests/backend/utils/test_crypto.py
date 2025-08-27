from __future__ import annotations

import importlib
from collections.abc import Callable, Generator

import pytest
from _pytest.monkeypatch import MonkeyPatch
from cryptography.fernet import Fernet, InvalidToken

from agentic_scraper.backend.core import settings as settings_module
from agentic_scraper.backend.utils import crypto as crypto_mod


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = "hello world"
    token = crypto_mod.encrypt(plaintext)
    assert isinstance(token, str)
    assert token != plaintext  # ciphertext should differ

    out = crypto_mod.decrypt(token)
    assert out == plaintext


def test_encrypt_is_nondeterministic_iv() -> None:
    plaintext = "repeat me"
    t1 = crypto_mod.encrypt(plaintext)
    t2 = crypto_mod.encrypt(plaintext)
    # Fernet uses a random IV; tokens should differ most of the time
    assert t1 != t2


def test_unicode_roundtrip() -> None:
    text = "héllø 👋 你好"
    token = crypto_mod.encrypt(text)
    assert crypto_mod.decrypt(token) == text


def test_decrypt_with_wrong_key_raises_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    plaintext = "secret"
    token = crypto_mod.encrypt(plaintext)

    # Swap out the module's Fernet with one using a different key
    other = Fernet(Fernet.generate_key())
    monkeypatch.setattr(crypto_mod, "fernet", other, raising=True)

    with pytest.raises(InvalidToken):
        crypto_mod.decrypt(token)


@pytest.fixture
def reload_crypto_with_key(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """
    Temporarily allow tests to mutate the crypto module's key.
    We back up and restore the module-level 'fernet' to avoid import/reload side effects.
    """
    import agentic_scraper.backend.utils.crypto as crypto_ref
    original_fernet = crypto_ref.fernet
    try:
        yield
    finally:
        crypto_ref.fernet = original_fernet


def test_module_uses_current_settings_key(
    monkeypatch: MonkeyPatch,
    settings: settings_module.Settings,
    reload_settings: Callable[[dict[str, str]], None],
    reload_crypto_with_key: None,
) -> None:
    from agentic_scraper.backend.utils import crypto as crypto_ref

    # Use a fresh, valid Fernet key string
    new_key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("ENCRYPTION_SECRET", new_key)
    reload_settings({"ENCRYPTION_SECRET": new_key})

    # Reload the crypto module so it re-reads settings and rebuilds Fernet
    importlib.reload(crypto_ref)

    msg = "ping"
    enc = crypto_ref.encrypt(msg)
    assert crypto_ref.decrypt(enc) == msg
