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
    MSG_WARNING_CREDENTIALS_NOT_FOUND,
)
from agentic_scraper.backend.core.logger_setup import get_logger
from agentic_scraper.backend.scraper.models import OpenAIConfig
from agentic_scraper.backend.utils.crypto import decrypt, encrypt

# Initialize logger for error logging
logger = get_logger()

# File path to local encrypted user credential store
USER_STORE = Path(".cache/user_store.json")
USER_STORE.parent.mkdir(parents=True, exist_ok=True)

# Create an empty store file if it does not exist
if not USER_STORE.exists():
    USER_STORE.write_text("{}")

def _load_store() -> dict[str, dict[str, str]]:
    """Loads the user store from file."""
    try:
        return cast("dict[str, dict[str, str]]", json.loads(USER_STORE.read_text()))
    except json.JSONDecodeError as e:
        logger.exception(MSG_ERROR_LOADING_USER_STORE, exc_info=e)
        return {}

def _save_store(store: dict[str, dict[str, str]]) -> None:
    """Saves the user store to file."""
    try:
        with tempfile.NamedTemporaryFile("w", dir=USER_STORE.parent, delete=False) as tmp:
            json.dump(store, tmp, indent=2)
            tmp.flush()
            Path(tmp.name).replace(USER_STORE)
    except OSError as e:  # Catch specific OSError
        error_message = MSG_ERROR_SAVING_USER_STORE.format(error=str(e))
        logger.exception(error_message, exc_info=e)  # Use exception logging
        raise OSError(error_message) from e
    except Exception as e:
        error_message = MSG_ERROR_SAVING_USER_STORE.format(error=str(e))
        logger.exception(error_message, exc_info=e)  # Use exception logging
        raise OSError(error_message) from e


def save_user_credentials(user_id: str, api_key: str, project_id: str) -> None:
    """Encrypts and saves the user's OpenAI credentials."""
    store = _load_store()
    try:
        store[user_id] = {
            "api_key": encrypt(api_key),
            "project_id": encrypt(project_id),
        }
        _save_store(store)
    except Exception as e:
        error_message = MSG_ERROR_INVALID_CREDENTIALS.format(user_id=user_id, error=str(e))
        logger.exception(error_message, exc_info=e)  # Use exception logging
        raise HTTPException(
            status_code=400, detail="Error saving credentials"
        ) from e


def load_user_credentials(user_id: str) -> OpenAIConfig | None:
    """Loads and decrypts the user's OpenAI credentials."""
    store = _load_store()
    user_data = store.get(user_id)
    if not user_data:
        logger.warning(MSG_WARNING_CREDENTIALS_NOT_FOUND.format(user_id=user_id))
        return None  # No credentials found for this user

    try:
        decrypted_api_key = decrypt(user_data["api_key"])
        decrypted_project_id = decrypt(user_data["project_id"])
        return OpenAIConfig(api_key=decrypted_api_key, project_id=decrypted_project_id)
    except Exception as e:
        error_message = MSG_ERROR_DECRYPTION_FAILED.format(user_id=user_id, error=str(e))
        logger.exception(error_message, exc_info=e)  # Use exception logging
        return None  # Return None if decryption fails
