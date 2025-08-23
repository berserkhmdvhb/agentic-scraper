from __future__ import annotations

import json
import types
from pathlib import Path
from typing import Generator

import pytest
from fastapi import HTTPException
from _pytest.logging import LogCaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from agentic_scraper.backend.api.stores import user_store as us
from agentic_scraper.backend.config.messages import (
    MSG_ERROR_DECRYPTION_FAILED,
    MSG_ERROR_SAVING_USER_STORE,
    MSG_INFO_CREDENTIALS_DELETED,
    MSG_WARNING_CREDENTIALS_NOT_FOUND,
)


@pytest.fixture
def user_store_tmp(monkeypatch: MonkeyPatch, tmp_path: Path) -> Generator[types.ModuleType, None, None]:
    """
    Point the user store at an isolated temp file for each test.
    Ensures the directory and an empty JSON object exist.
    """
    store_dir = tmp_path / ".cache"
    store_dir.mkdir(parents=True, exist_ok=True)
    store_file = store_dir / "user_store.json"
    store_file.write_text("{}")

    # Patch the module-level constant to our temp file
    monkeypatch.setattr(us, "USER_STORE", store_file, raising=True)
    us.USER_STORE.parent.mkdir(parents=True, exist_ok=True)

    yield us


def test_save_and_load_roundtrip(user_store_tmp: types.ModuleType) -> None:
    us_mod = user_store_tmp

    user_id = "auth0|u1"
    api_key = "sk-test-123"
    project_id = "proj-abc"

    us_mod.save_user_credentials(user_id, api_key, project_id)
    cfg = us_mod.load_user_credentials(user_id)

    assert cfg is not None
    assert cfg.api_key == api_key
    assert cfg.project_id == project_id

    # Ensure ciphertext is not plaintext on disk
    on_disk = json.loads(Path(us_mod.USER_STORE).read_text())
    assert user_id in on_disk
    assert on_disk[user_id]["api_key"] != api_key
    assert on_disk[user_id]["project_id"] != project_id
    assert on_disk[user_id]["api_key"]
    assert on_disk[user_id]["project_id"]


def test_load_missing_returns_none_and_logs_warning(
    user_store_tmp: types.ModuleType, caplog_debug: LogCaptureFixture
) -> None:
    us_mod = user_store_tmp

    res = us_mod.load_user_credentials("unknown-user")
    assert res is None

    assert any(
        MSG_WARNING_CREDENTIALS_NOT_FOUND.format(user_id="unknown-user") in r.message
        for r in caplog_debug.records
    )


def test_has_user_credentials(user_store_tmp: types.ModuleType) -> None:
    us_mod = user_store_tmp
    assert us_mod.has_user_credentials("u1") is False
    us_mod.save_user_credentials("u1", "sk", "p1")
    assert us_mod.has_user_credentials("u1") is True
    assert us_mod.has_user_credentials("u2") is False


def test_delete_missing_returns_false_and_logs_warning(
    user_store_tmp: types.ModuleType, caplog_debug: LogCaptureFixture
) -> None:
    us_mod = user_store_tmp

    ok = us_mod.delete_user_credentials("ghost")
    assert ok is False
    assert any(
        MSG_WARNING_CREDENTIALS_NOT_FOUND.format(user_id="ghost") in r.message
        for r in caplog_debug.records
    )


def test_delete_existing_success(
    user_store_tmp: types.ModuleType, caplog_debug: LogCaptureFixture
) -> None:
    us_mod = user_store_tmp
    us_mod.save_user_credentials("u1", "sk", "p1")

    ok = us_mod.delete_user_credentials("u1")
    assert ok is True
    assert us_mod.has_user_credentials("u1") is False

    assert any(
        MSG_INFO_CREDENTIALS_DELETED.format(user_id="u1") in r.message
        for r in caplog_debug.records
    )


def test_overwrite_existing_credentials(user_store_tmp: types.ModuleType) -> None:
    us_mod = user_store_tmp
    us_mod.save_user_credentials("u1", "sk-1", "p-1")
    us_mod.save_user_credentials("u1", "sk-2", "p-2")

    cfg = us_mod.load_user_credentials("u1")
    assert cfg is not None
    assert cfg.api_key == "sk-2"
    assert cfg.project_id == "p-2"


def test_multiple_users_isolated(user_store_tmp: types.ModuleType) -> None:
    us_mod = user_store_tmp
    us_mod.save_user_credentials("u1", "sk-1", "p-1")
    us_mod.save_user_credentials("u2", "sk-2", "p-2")

    c1 = us_mod.load_user_credentials("u1")
    c2 = us_mod.load_user_credentials("u2")

    assert c1 is not None and c1.api_key == "sk-1" and c1.project_id == "p-1"
    assert c2 is not None and c2.api_key == "sk-2" and c2.project_id == "p-2"


def test_corrupted_store_file_is_handled_gracefully(user_store_tmp: types.ModuleType) -> None:
    us_mod = user_store_tmp

    # Corrupt the file with invalid JSON
    Path(us_mod.USER_STORE).write_text("{ this is not: valid json")

    # No exception on load; just treat as empty and return None
    assert us_mod.load_user_credentials("u1") is None

    # Saving after corruption should rewrite a valid store
    us_mod.save_user_credentials("u1", "sk", "p")
    data = json.loads(Path(us_mod.USER_STORE).read_text())
    assert "u1" in data


def test_decryption_failure_returns_none_and_logs_error(
    user_store_tmp: types.ModuleType, caplog_debug: LogCaptureFixture
) -> None:
    us_mod = user_store_tmp

    # Manually write invalid ciphertext payloads
    bad_store = {
        "u1": {
            "api_key": "not-a-ciphertext",
            "project_id": "still-not-a-ciphertext",
        }
    }
    Path(us_mod.USER_STORE).write_text(json.dumps(bad_store))

    res = us_mod.load_user_credentials("u1")
    assert res is None

    # Should log decryption failure message (allow variable error text suffix)
    prefix = MSG_ERROR_DECRYPTION_FAILED.format(user_id="u1", error="")
    assert any(prefix[:-1] in r.message for r in caplog_debug.records)


def test_save_user_credentials_bubbles_http_exception_on_save_error(
    user_store_tmp: types.ModuleType, monkeypatch: MonkeyPatch
) -> None:
    us_mod = user_store_tmp

    def _boom(_store: dict[str, dict[str, str]]) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(us_mod, "_save_store", _boom, raising=True)

    with pytest.raises(HTTPException) as exc:
        us_mod.save_user_credentials("u1", "sk", "p")

    assert exc.value.status_code == 400  # as implemented in save_user_credentials()


def test__save_store_raises_oserror_with_formatted_message(
    user_store_tmp: types.ModuleType, monkeypatch: MonkeyPatch
) -> None:
    us_mod = user_store_tmp

    def dump_boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(json, "dump", dump_boom, raising=True)

    with pytest.raises(OSError) as exc:
        us_mod._save_store({"u1": {"api_key": "x", "project_id": "y"}})

    # Should include the formatted constant-based message prefix
    assert MSG_ERROR_SAVING_USER_STORE.split("{error}")[0] in str(exc.value)
