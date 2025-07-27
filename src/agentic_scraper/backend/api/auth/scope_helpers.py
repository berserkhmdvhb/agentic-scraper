import logging

from fastapi.security import HTTPBearer

from agentic_scraper.backend.api.models import AuthUser, RequiredScopes
from agentic_scraper.backend.api.utils.log_helpers import raise_forbidden
from agentic_scraper.backend.config.messages import (
    MSG_DEBUG_MISSING_SCOPES,
    MSG_ERROR_USER_SCOPES_TYPE,
)

# Initialize logger
logger = logging.getLogger(__name__)

auth_scheme = HTTPBearer(auto_error=True)

# Function to check if user has the required scope using the RequiredScopes Enum
def check_required_scopes(payload: AuthUser, required_scopes: set[RequiredScopes]) -> None:
    """
    Validate if the token contains the required scopes from the `RequiredScopes` enum.

    Args:
        payload (AuthUser): Decoded JWT payload containing user information.
        required_scopes (set[RequiredScopes]): Set of required scopes.

    Raises:
        HTTPException: If any of the required scopes are missing from the payload.
    """
    # Extract the "scope" from the payload
    user_scopes: str | list[str] = payload.get("scope", "")

    # If scope is a string, split it into a list of strings
    if isinstance(user_scopes, str):
        user_scopes = user_scopes.split()

    # Ensure user_scopes is a list of strings
    if not isinstance(user_scopes, list):
        raise TypeError(MSG_ERROR_USER_SCOPES_TYPE.format(user_scopes=user_scopes))

    # Convert user_scopes into a set for efficient scope checking
    user_scopes_set = set(user_scopes)

    # Check if all required scopes are in user_scopes
    missing_scopes = [
        scope.value
        for scope in required_scopes
        if scope.value not in user_scopes_set
    ]

    if missing_scopes:
        # Log the missing scopes and the user's current scopes
        logger.debug(MSG_DEBUG_MISSING_SCOPES.format(
            missing_scopes=" ".join(missing_scopes),
            user_scopes=" ".join(user_scopes),
        ))

        # Raise HTTPException if required scopes are missing
        raise_forbidden(required_scopes=missing_scopes)
