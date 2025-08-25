import logging
from typing import NoReturn

from fastapi import HTTPException, status
from jose import JWTError

from agentic_scraper.backend.config.messages import (
    MSG_ERROR_INTERNAL_SERVER,
    MSG_ERROR_INVALID_TOKEN,
    MSG_ERROR_MISSING_SCOPES,
    MSG_INFO_USER_AUTHORIZED,
    MSG_WARNING_INSUFFICIENT_PERMISSIONS,
    MSG_WARNING_USER_FAILED_AUTHORIZATION,
)

# Initialize logger
logger = logging.getLogger(__name__)


def raise_forbidden(required_scopes: list[str]) -> None:
    """
    Raise a 403 Forbidden HTTPException due to insufficient permissions.

    Logs a warning and raises an exception with the appropriate status code and
    error message.

    Args:
        required_scopes (list[str]): List of required scopes that the user needs.
    """
    required_scopes_str = " ".join(required_scopes)
    logger.warning(MSG_WARNING_INSUFFICIENT_PERMISSIONS.format(scopes=required_scopes_str))
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=MSG_ERROR_MISSING_SCOPES.format(scopes=required_scopes_str),
        headers={"WWW-Authenticate": "Bearer"},
    )


def raise_unauthorized(err: JWTError) -> None:
    """
    Raise a 401 Unauthorized HTTPException due to invalid or expired JWT.

    Logs the error message and raises an exception with the appropriate status code.

    Args:
        err (JWTError): The exception raised during the JWT verification process.
    """
    logger.exception(MSG_ERROR_INVALID_TOKEN.format(error=str(err)))
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    ) from err


def raise_internal_error(e: Exception) -> NoReturn:
    """
    Raise a 500 Internal Server Error HTTPException.

    Logs the error message and raises an exception with the appropriate status code
    for unexpected issues.

    Args:
        e (Exception): The exception encountered during the JWT verification process.
    """
    logger.exception(MSG_ERROR_INTERNAL_SERVER.format(error=str(e)), exc_info=e)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error during token validation",
        headers={"WWW-Authenticate": "Bearer"},
    ) from e


def log_raise_info(message: str, **kwargs: object) -> None:
    """
    Log an info-level message.

    Args:
        message (str): The message to log.
        kwargs: Additional context to include in the log.
    """
    logger.info(message, extra=kwargs)


def log_raise_warning(message: str, **kwargs: object) -> None:
    """
    Log a warning-level message.

    Args:
        message (str): The message to log.
        kwargs: Additional context to include in the log.
    """
    logger.warning(message, extra=kwargs)


def log_raise_error(message: str, **kwargs: object) -> None:
    """
    Log an error-level message.

    Args:
        message (str): The message to log.
        kwargs: Additional context to include in the log.
    """
    logger.exception(message, extra=kwargs)


def log_raise_user_authorization(user_id: str, *, success: bool) -> None:
    """
    Log user authorization success or failure.

    Args:
        user_id (str): The ID of the user.
        success (bool): Whether the authorization was successful.
    """
    if success:
        log_raise_info(MSG_INFO_USER_AUTHORIZED.format(user_id=user_id))
    else:
        log_raise_warning(MSG_WARNING_USER_FAILED_AUTHORIZATION.format(user_id=user_id))
