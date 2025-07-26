import json
import tempfile
from pathlib import Path
from typing import cast

from agentic_scraper.backend.scraper.models import OpenAIConfig
from agentic_scraper.backend.utils.crypto import decrypt, encrypt

# File path to local encrypted user credential store
USER_STORE = Path(".cache/user_store.json")
USER_STORE.parent.mkdir(parents=True, exist_ok=True)

if not USER_STORE.exists():
    USER_STORE.write_text("{}")


def _load_store() -> dict[str, dict[str, str]]:
    try:
        # Use cast to explicitly specify the return type for json.loads
        return cast("dict[str, dict[str, str]]", json.loads(USER_STORE.read_text()))
    except json.JSONDecodeError:
        # If corrupted, fallback to empty store
        return {}


def _save_store(store: dict[str, dict[str, str]]) -> None:
    with tempfile.NamedTemporaryFile("w", dir=USER_STORE.parent, delete=False) as tmp:
        json.dump(store, tmp, indent=2)
        tmp.flush()
        Path(tmp.name).replace(USER_STORE)


def save_user_credentials(user_id: str, api_key: str, project_id: str) -> None:
    store = _load_store()
    store[user_id] = {
        "api_key": encrypt(api_key),
        "project_id": encrypt(project_id),
    }
    _save_store(store)


def load_user_credentials(user_id: str) -> OpenAIConfig | None:
    store = _load_store()
    user_data = store.get(user_id)
    if not user_data:
        return None
    return OpenAIConfig(
        api_key=decrypt(user_data["api_key"]),
        project_id=decrypt(user_data["project_id"]),
    )
