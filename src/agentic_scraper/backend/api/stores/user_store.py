"""
Handles secure storage and retrieval of user credentials for OpenAI access.

Responsibilities:
- Encrypt and store user credentials (API key and project ID) on disk.
- Decrypt and retrieve credentials for authenticated sessions.
- Maintain a simple JSON-based, process-local credential store.

Public API:
- `save_user_credentials`: Encrypt and persist credentials for a user.
- `load_user_credentials`: Decrypt and return credentials if present.
- `delete_user_credentials`: Remove stored credentials for a user.
- `has_user_credentials`: Check presence of stored credentials.

Operational:
- Concurrency: Process-local; external synchronization not provided.
- Logging: Uses message constants; secrets are never logged.

Usage:
    from agentic_scraper.backend.api.stores.user_store import (
        save_user_credentials,
        load_user_credentials,
    )
    save_user_credentials(user_id="auth0|abc123", api_key="sk-...", project_id="proj_...")
    cfg = load_user_credentials("auth0|abc123")

Notes:
- Credentials are encrypted at rest and written atomically via a temp file to avoid partial writes.
- The store is a single JSON file keyed by user_id (Auth0 subject).
- I/O and crypto errors are logged using message constants for consistency.
- These helpers are filesystem-bound and process-local; no network I/O occurs here.
"""

import json
import tempfile
from pathlib import Path
from typing import cast

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_DECRYPTION_FAILED,
    MSG_ERROR_LOADING_USER_STORE,
    MSG_ERROR_SAVING_USER_STORE,
    MSG_INFO_CREDENTIALS_DELETED,
    MSG_WARNING_CREDENTIALS_NOT_FOUND,
)
from agentic_scraper.backend.config.types import OpenAIConfig
from agentic_scraper.backend.core.logger_setup import get_logger
from agentic_scraper.backend.utils.crypto import decrypt, encrypt
from agentic_scraper.backend.utils.validators import (
    ensure_directory,
    validate_openai_credentials_pair,
    validate_user_id,
)

logger = get_logger()

# Location of the on-disk store. Consider mapping this to an app-specific data dir
# in production. For local dev, a project-relative .cache directory is convenient.
USER_STORE: Path = Path(".cache/user_store.json")

# Ensure the parent directory exists early to avoid race-y "file not found" errors later.
ensure_directory(USER_STORE.parent)

# Bootstrap an empty JSON store if none exists (idempotent).
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
        dict[str, dict[str, str]]: Mapping of user IDs to encrypted credential dicts,
        each with "api_key" and "project_id" ciphertext strings.

    Raises:
        json.JSONDecodeError: If the store is malformed (caught internally and logged).
                              In this case an empty store is returned.

    Notes:
        - Fail-soft behavior returns `{}` on decode errors to keep API surfaces stable.
    """
    try:
        # Use `cast` to inform type checkers the JSON is expected to be a two-level dict of strings.
        return cast("dict[str, dict[str, str]]", json.loads(USER_STORE.read_text()))
    except json.JSONDecodeError as e:
        # Corrupted or manually-edited store file; fail soft with an empty store.
        logger.exception(MSG_ERROR_LOADING_USER_STORE, exc_info=e)
        return {}


def _save_store(store: dict[str, dict[str, str]]) -> None:
    """
    Save the encrypted user credential store safely to disk.

    Uses a temporary file for atomic write operations to avoid partial writes on crash.

    Args:
        store (dict[str, dict[str, str]]): Encrypted credentials mapped by user ID.

    Returns:
        None

    Raises:
        OSError: If saving fails due to file system errors or encoding issues.

    Notes:
        - Write temp file in the same directory to ensure atomic replace works across filesystems.
    """
    try:
        # Write to a temp file in the same directory to ensure
        # atomic replace works across filesystems.
        with tempfile.NamedTemporaryFile("w", dir=USER_STORE.parent, delete=False) as tmp:
            json.dump(store, tmp, indent=2)
            tmp.flush()
            tmp.close()
            # Atomic replace on most POSIX/NTFS systems.
            Path(tmp.name).replace(USER_STORE)
    except OSError as e:
        error_message = MSG_ERROR_SAVING_USER_STORE.format(error=str(e))
        logger.exception(error_message, exc_info=e)
        raise OSError(error_message) from e
    except Exception as e:
        # Catch-all for unexpected serialization or write errors.
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

    Returns:
        None

    Raises:
        ValueError: If inputs are invalid (via validators for user_id and credentials).
        OSError: If credentials cannot be saved due to I/O or serialization errors.

    Notes:
        - Inputs are validated before any I/O occurs.
        - Secrets are encrypted independently for defense in depth.
    """
    # Validate inputs early; these raise ValueError with helpful messages.
    user_id = validate_user_id(user_id)
    api_key, project_id = validate_openai_credentials_pair(api_key, project_id)

    # Load, update, and persist the store with encrypted material.
    store = _load_store()
    try:
        store[user_id] = {
            "api_key": encrypt(api_key),
            "project_id": encrypt(project_id),
        }
        _save_store(store)
    except Exception as e:
        # Surface as OSError so the route layer can convert to HTTP appropriately.
        error_message = MSG_ERROR_SAVING_USER_STORE.format(error=str(e))
        logger.exception(error_message, exc_info=e)
        raise OSError(error_message) from e


def load_user_credentials(user_id: str) -> OpenAIConfig | None:
    """
    Load and decrypt OpenAI credentials for a user.

    Args:
        user_id (str): The user's Auth0 subject ID.

    Returns:
        OpenAIConfig | None: Decrypted credentials if available and valid; otherwise None.
                             Fail-soft behavior logs errors and returns None.

    Raises:
        ValueError: If the user_id is invalid (via validator).

    Notes:
        - Decryption exceptions are caught and logged; `None` is returned to avoid leaking details.
    """
    user_id = validate_user_id(user_id)
    store = _load_store()
    user_data = store.get(user_id)
    if not user_data:
        logger.warning(MSG_WARNING_CREDENTIALS_NOT_FOUND.format(user_id=user_id))
        return None

    try:
        decrypted_api_key = decrypt(user_data["api_key"])
        decrypted_project_id = decrypt(user_data["project_id"])
        # Return a typed config object that callers can pass directly into settings/clients.
        return OpenAIConfig(api_key=decrypted_api_key, project_id=decrypted_project_id)
    except Exception as e:
        # Decryption can fail if the key/nonce changes or the ciphertext is corrupted.
        error_message = MSG_ERROR_DECRYPTION_FAILED.format(user_id=user_id, error=str(e))
        logger.exception(error_message, exc_info=e)
        return None


def delete_user_credentials(user_id: str) -> bool:
    """
    Delete stored OpenAI credentials for the given user.

    Args:
        user_id (str): The user's Auth0 subject ID.

    Returns:
        bool: True if credentials were deleted, False if no credentials existed.

    Raises:
        ValueError: If inputs are invalid (via validator).
        OSError: If deletion or saving fails due to file I/O issues.

    Notes:
        - Missing entries are not an error; returns False after warning.
    """
    user_id = validate_user_id(user_id)
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
    user_id = validate_user_id(user_id)
    store = _load_store()
    return user_id in store
