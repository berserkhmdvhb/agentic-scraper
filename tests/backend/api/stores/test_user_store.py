from __future__ import annotations

import json
from types import ModuleType
from typing import Any, cast

import pytest
from _pytest.logging import LogCaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_DECRYPTION_FAILED,
    MSG_ERROR_SAVING_USER_STORE,
    MSG_INFO_CREDENTIALS_DELETED,
    MSG_WARNING_CREDENTIALS_NOT_FOUND,
)
from agentic_scraper.backend.config.types import OpenAIConfig


def read_store_json(user_store_mod: ModuleType) -> dict[str, dict[str, str]]:
    loaded: Any = json.loads(user_store_mod.USER_STORE.read_text())
    return cast("dict[str, dict[str, str]]", loaded)


def test_save_and_load_roundtrip(user_store_mod: ModuleType, stub_crypto: None) -> None:
    user_id = "auth0|abc123"
    user_store_mod.save_user_credentials(user_id, "sk-test", "proj-xyz")
    assert user_store_mod.has_user_credentials(user_id) is True

    store = read_store_json(user_store_mod)
    assert store[user_id]["api_key"].startswith("enc:")
    assert store[user_id]["project_id"].startswith("enc:")

    cfg = user_store_mod.load_user_credentials(user_id)

    assert isinstance(cfg, OpenAIConfig)
    assert cfg.api_key == "sk-test"
    assert cfg.project_id == "proj-xyz"


def test_delete_credentials_success(
    user_store_mod: ModuleType,
    stub_crypto: None,
    caplog_debug: LogCaptureFixture,
) -> None:
    user_id = "auth0|to_delete"
    user_store_mod.save_user_credentials(user_id, "k", "p")

    ok = user_store_mod.delete_user_credentials(user_id)
    assert ok is True
    assert user_store_mod.has_user_credentials(user_id) is False

    logs = "\n".join(rec.getMessage() for rec in caplog_debug.records)
    assert MSG_INFO_CREDENTIALS_DELETED.format(user_id=user_id) in logs


def test_load_missing_credentials_logs_warning(
    user_store_mod: ModuleType,
    caplog_debug: LogCaptureFixture,
) -> None:
    user_id = "auth0|missing"
    out = user_store_mod.load_user_credentials(user_id)
    assert out is None

    logs = "\n".join(rec.getMessage() for rec in caplog_debug.records)
    assert MSG_WARNING_CREDENTIALS_NOT_FOUND.format(user_id=user_id) in logs


def test_delete_missing_credentials_returns_false_and_logs(
    user_store_mod: ModuleType,
    caplog_debug: LogCaptureFixture,
) -> None:
    user_id = "auth0|missing"
    ok = user_store_mod.delete_user_credentials(user_id)
    assert ok is False

    logs = "\n".join(rec.getMessage() for rec in caplog_debug.records)
    assert MSG_WARNING_CREDENTIALS_NOT_FOUND.format(user_id=user_id) in logs


def test_save_user_credentials_encrypt_failure_raises_http(
    user_store_mod: ModuleType,
    monkeypatch: MonkeyPatch,
) -> None:
    def _boom(_value: str) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(user_store_mod, "encrypt", _boom, raising=True)

    with pytest.raises(OSError) as e:
        user_store_mod.save_user_credentials("auth0|abc", "k", "p")
    # The store surfaces a generic OSError; routes map it to a 500.
    msg = str(e.value)
    assert "Failed to save user store" in msg
    assert "boom" in msg

def test_load_user_credentials_decrypt_failure_returns_none(
    user_store_mod: ModuleType,
    monkeypatch: MonkeyPatch,
    caplog_debug: LogCaptureFixture,
) -> None:
    user_id = "auth0|baddec"
    user_store_mod.USER_STORE.write_text(
        json.dumps({user_id: {"api_key": "bad", "project_id": "bad"}})
    )

    def _dec(_v: str) -> str:
        raise ValueError("cannot decrypt")

    monkeypatch.setattr(user_store_mod, "decrypt", _dec, raising=True)

    out = user_store_mod.load_user_credentials(user_id)
    assert out is None

    logs = "\n".join(rec.getMessage() for rec in caplog_debug.records)
    assert MSG_ERROR_DECRYPTION_FAILED.format(user_id=user_id, error="cannot decrypt") in logs


def test__load_store_with_malformed_json_returns_empty_dict(
    user_store_mod: ModuleType,
) -> None:
    user_store_mod.USER_STORE.write_text("{")
    assert user_store_mod._load_store() == {}


def test__save_store_ioerror_wraps_with_message(
    user_store_mod: ModuleType,
    monkeypatch: MonkeyPatch,
) -> None:
    def _raising_named_tmpfile(*args: object, **kwargs: object) -> object:
        raise OSError("disk full")

    monkeypatch.setattr(
        user_store_mod.tempfile, "NamedTemporaryFile", _raising_named_tmpfile, raising=True
    )

    with pytest.raises(OSError) as e:
        user_store_mod._save_store({"u": {"api_key": "x", "project_id": "y"}})

    assert MSG_ERROR_SAVING_USER_STORE.format(error="disk full") in str(e.value)


def test_has_user_credentials_true_false(user_store_mod: ModuleType, stub_crypto: None) -> None:
    uid = "auth0|x"
    assert user_store_mod.has_user_credentials(uid) is False
    user_store_mod.save_user_credentials(uid, "k", "p")
    assert user_store_mod.has_user_credentials(uid) is True


@pytest.mark.parametrize("bad", ["", "   ", None, 123])
def test_public_functions_validate_user_id(
    user_store_mod: ModuleType,
    stub_crypto: None,
    bad: Any,
) -> None:
    # All should raise ValueError via validate_user_id before any I/O
    import typing as _t

    with pytest.raises(ValueError):
        user_store_mod.save_user_credentials(_t.cast("str", bad), "k", "p")
    with pytest.raises(ValueError):
        user_store_mod.load_user_credentials(_t.cast("str", bad))
    with pytest.raises(ValueError):
        user_store_mod.delete_user_credentials(_t.cast("str", bad))
    with pytest.raises(ValueError):
        user_store_mod.has_user_credentials(_t.cast("str", bad))


@pytest.mark.parametrize(
    ("api", "proj"),
    [("", "p"), ("   ", "p"), (None, "p"), ("k", ""), ("k", "   "), ("k", None)],
)
def test_save_user_credentials_validates_pair(
    user_store_mod: ModuleType,
    api: Any,
    proj: Any,
) -> None:
    import typing as _t

    with pytest.raises(ValueError):
        user_store_mod.save_user_credentials("auth0|ok", _t.cast("str", api), _t.cast("str", proj))
