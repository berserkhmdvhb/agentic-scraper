"""
Handles secure storage and retrieval of user credentials for OpenAI access.

This module provides utilities to:
- Encrypt and store user credentials (API key and project ID) on disk.
- Decrypt and retrieve them later during authenticated user sessions.
- Use a local JSON file as a simple encrypted user credential store.

Credentials are encrypted before being saved and safely written via a temp file.
Errors during storage or decryption are logged and handled gracefully.
"""

import json
import tempfile
from pathlib import Path
from typing import cast

from fastapi import HTTPException

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_DECRYPTION_FAILED,
    MSG_ERROR_INVALID_CREDENTIALS,
    MSG_ERROR_LOADING_USER_STORE,
    MSG_ERROR_SAVING_USER_STORE,
    MSG_INFO_CREDENTIALS_DELETED,
    MSG_WARNING_CREDENTIALS_NOT_FOUND,
)
from agentic_scraper.backend.config.types import OpenAIConfig
from agentic_scraper.backend.core.logger_setup import get_logger
from agentic_scraper.backend.utils.crypto import decrypt, encrypt

logger = get_logger()

USER_STORE = Path(".cache/user_store.json")
USER_STORE.parent.mkdir(parents=True, exist_ok=True)

if not USER_STORE.exists():
    USER_STORE.write_text("{}")

__all__ = [
    "delete_user_credentials",
    "has_user_credentials",
    "load_user_credentials",
    "save_user_credentials",
]


def _load_store() -> dict[str, dict[str, str]]:
    """
    Load the encrypted user store from disk.

    Returns:
        dict[str, dict[str, str]]: Dictionary mapping user IDs to encrypted credential dicts.

    Raises:
        json.JSONDecodeError: If the store is malformed (caught internally and logged).
    """
    try:
        return cast("dict[str, dict[str, str]]", json.loads(USER_STORE.read_text()))
    except json.JSONDecodeError as e:
        logger.exception(MSG_ERROR_LOADING_USER_STORE, exc_info=e)
        return {}


def _save_store(store: dict[str, dict[str, str]]) -> None:
    """
    Save the encrypted user credential store safely to disk.

    Uses a temporary file for atomic write operations.

    Args:
        store (dict[str, dict[str, str]]): Encrypted credentials mapped by user ID.

    Raises:
        OSError: If saving fails due to file system errors or encoding issues.
    """
    try:
        with tempfile.NamedTemporaryFile("w", dir=USER_STORE.parent, delete=False) as tmp:
            json.dump(store, tmp, indent=2)
            tmp.flush()
            tmp.close()
            Path(tmp.name).replace(USER_STORE)
    except OSError as e:
        error_message = MSG_ERROR_SAVING_USER_STORE.format(error=str(e))
        logger.exception(error_message, exc_info=e)
        raise OSError(error_message) from e
    except Exception as e:
        # Catch-all for unexpected serialization or write errors
        error_message = MSG_ERROR_SAVING_USER_STORE.format(error=str(e))
        logger.exception(error_message, exc_info=e)
        raise OSError(error_message) from e


def save_user_credentials(user_id: str, api_key: str, project_id: str) -> None:
    """
    Encrypt and persist OpenAI credentials for a user.

    Args:
        user_id (str): The user's Auth0 subject ID.
        api_key (str): OpenAI API key to encrypt and store.
        project_id (str): OpenAI project ID to encrypt and store.

    Raises:
        HTTPException: If credentials cannot be saved or encrypted.
    """
    store = _load_store()
    try:
        store[user_id] = {
            "api_key": encrypt(api_key),
            "project_id": encrypt(project_id),
        }
        _save_store(store)
    except Exception as e:
        error_message = MSG_ERROR_INVALID_CREDENTIALS.format(user_id=user_id, error=str(e))
        logger.exception(error_message, exc_info=e)
        raise HTTPException(status_code=400, detail="Error saving credentials") from e


def load_user_credentials(user_id: str) -> OpenAIConfig | None:
    """
    Load and decrypt OpenAI credentials for a user.

    Args:
        user_id (str): The user's Auth0 subject ID.

    Returns:
        OpenAIConfig | None: Decrypted credentials if available and valid, otherwise None.

    Raises:
        Exception: If decryption fails internally (returns None but logs exception).
    """
    store = _load_store()
    user_data = store.get(user_id)
    if not user_data:
        logger.warning(MSG_WARNING_CREDENTIALS_NOT_FOUND.format(user_id=user_id))
        return None

    try:
        decrypted_api_key = decrypt(user_data["api_key"])
        decrypted_project_id = decrypt(user_data["project_id"])
        return OpenAIConfig(api_key=decrypted_api_key, project_id=decrypted_project_id)
    except Exception as e:
        error_message = MSG_ERROR_DECRYPTION_FAILED.format(user_id=user_id, error=str(e))
        logger.exception(error_message, exc_info=e)
        return None


def delete_user_credentials(user_id: str) -> bool:
    """
    Delete stored OpenAI credentials for the given user.

    Args:
        user_id (str): The user's Auth0 subject ID.

    Returns:
        bool: True if credentials were deleted, False if not found.

    Raises:
        OSError: If deletion or saving fails due to file I/O issues.
    """
    store = _load_store()

    if user_id not in store:
        logger.warning(MSG_WARNING_CREDENTIALS_NOT_FOUND.format(user_id=user_id))
        return False

    try:
        del store[user_id]
        _save_store(store)
        logger.info(MSG_INFO_CREDENTIALS_DELETED.format(user_id=user_id))
    except Exception as e:
        error_message = MSG_ERROR_SAVING_USER_STORE.format(error=str(e))
        logger.exception(error_message, exc_info=e)
        raise OSError(error_message) from e
    else:
        return True


def has_user_credentials(user_id: str) -> bool:
    """
    Check if the given user has stored OpenAI credentials.

    Args:
        user_id (str): The user's Auth0 subject ID.

    Returns:
        bool: True if credentials exist, False otherwise.
    """
    store = _load_store()
    return user_id in store
