"""Domain exceptions and the handlers that turn them into one JSON envelope:
{"error": {"code": ..., "message": ..., "details": ...}}"""

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}


class ListingNotFoundError(AppError):
    status_code = 404
    code = "listing_not_found"

    def __init__(self, listing_id: uuid.UUID) -> None:
        super().__init__("Listing not found", {"listing_id": str(listing_id)})


class ModelNotFoundError(AppError):
    status_code = 404
    code = "model_not_found"

    def __init__(self, model: str) -> None:
        super().__init__("Model not found", {"model": model})


class InvalidSearchError(AppError):
    status_code = 422
    code = "invalid_search"


class NoComparablesError(AppError):
    status_code = 422
    code = "no_comparables"

    def __init__(self, tried: list[str]) -> None:
        super().__init__("Not enough comparable listings", {"tried": tried})


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"


class AssistantUnavailableError(AppError):
    """No model configured, or the provider failed. The chat never answers from a
    canned script, so this is what an outage looks like to the caller."""

    status_code = 503
    code = "assistant_unavailable"

    def __init__(self) -> None:
        super().__init__("The assistant is unavailable")


class AnonymousChatLimitError(AppError):
    status_code = 429
    code = "anonymous_chat_limit"

    def __init__(self, limit: int, retry_after: int) -> None:
        super().__init__(
            "برای ادامهٔ گفتگو وارد حساب کاربری‌ات شو؛ سهمیهٔ روزانهٔ مهمان تمام شده.",
            {"limit": limit, "retry_after_seconds": retry_after},
        )


class IngestError(AppError):
    code = "ingest_failed"


class InvalidCredentialsError(AppError):
    status_code = 401
    code = "invalid_credentials"

    def __init__(self) -> None:
        # One message for "no such user" and "wrong password": never say which.
        super().__init__("Invalid email or password")


class NotAuthenticatedError(AppError):
    status_code = 401
    code = "not_authenticated"

    def __init__(self) -> None:
        super().__init__("Not authenticated")


class TokenExpiredError(AppError):
    status_code = 401
    code = "token_expired"

    def __init__(self) -> None:
        super().__init__("Token expired")


class AccountDisabledError(AppError):
    status_code = 403
    code = "account_disabled"

    def __init__(self) -> None:
        super().__init__("Account disabled")


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"

    def __init__(self) -> None:
        super().__init__("Permission denied")


class EmailAlreadyRegisteredError(AppError):
    status_code = 409
    code = "email_taken"

    def __init__(self) -> None:
        super().__init__("Email already registered")


class AlertNotFoundError(AppError):
    status_code = 404
    code = "alert_not_found"

    def __init__(self, alert_id: uuid.UUID) -> None:
        super().__init__("Alert not found", {"alert_id": str(alert_id)})


class ChatNotFoundError(AppError):
    status_code = 404
    code = "chat_not_found"

    def __init__(self, chat_id: uuid.UUID) -> None:
        super().__init__("Chat not found", {"chat_id": str(chat_id)})


class AdminReauthRequiredError(AppError):
    status_code = 403
    code = "admin_reauth_required"

    def __init__(self) -> None:
        # Distinct from permission_denied: the caller IS an admin, their password
        # entry is just too old. The UI shows a password prompt, not a dead end.
        super().__init__("Re-authentication required")


class CannotModifySelfError(AppError):
    status_code = 409
    code = "cannot_modify_self"

    def __init__(self) -> None:
        super().__init__("An admin cannot disable, demote or delete themselves")


class LastAdminError(AppError):
    status_code = 409
    code = "last_admin"

    def __init__(self) -> None:
        super().__init__("The last active admin cannot be disabled, demoted or deleted")


class AdminUserNotFoundError(AppError):
    status_code = 404
    code = "admin_user_not_found"

    def __init__(self, user_id: uuid.UUID) -> None:
        super().__init__("User not found", {"user_id": str(user_id)})


def invalid_search_error(message: str, error: ValidationError) -> InvalidSearchError:
    """A pydantic ValidationError raised while building a SearchIntent from
    user-supplied input (query params, free-text query) is a 422, not a 500.
    Only call this at an actual user-input boundary — not for a corrupted cache
    payload, which must stay a 500."""
    # "input" is the raw user value and must never ride back out in an envelope;
    # "url" and "ctx" are noise. Filtered by key rather than by keyword argument so
    # this path and _handle_validation_error below share one mechanism.
    noise = {"input", "url", "ctx"}
    details = [
        {key: value for key, value in entry.items() if key not in noise}
        for entry in error.errors()
    ]
    return InvalidSearchError(message, {"errors": details})


def _envelope(status_code: int, code: str, message: str, details: Any) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details}}
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


def _handle_app_error(_: Request, error: AppError) -> JSONResponse:
    response = _envelope(error.status_code, error.code, error.message, error.context)
    if isinstance(error, AnonymousChatLimitError):
        response.headers["Retry-After"] = str(error.context["retry_after_seconds"])
    return response


def _handle_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
    # `error.errors()` includes the raw submitted value under "input" — for a password
    # field that is the plaintext password. Strip it before it reaches any log, APM or
    # error tracker; loc/msg/type stay so the response is still useful. Filtering by
    # key (rather than by keyword argument) also keeps this identical to
    # invalid_search_error above, and works for RequestValidationError, whose
    # errors() takes no kwargs at all.
    details = [
        {key: value for key, value in entry.items() if key != "input"}
        for entry in error.errors()
    ]
    return _envelope(422, "validation_error", "Invalid request", details)


def _handle_http_error(_: Request, error: StarletteHTTPException) -> JSONResponse:
    return _envelope(error.status_code, "http_error", str(error.detail), {})


def _handle_database_down(_: Request, error: OperationalError) -> JSONResponse:
    logger.error("database unavailable", exc_info=error)
    unavailable = ServiceUnavailableError("Database unavailable")
    return _envelope(unavailable.status_code, unavailable.code, unavailable.message, {})


def _handle_unexpected(_: Request, error: Exception) -> JSONResponse:
    logger.error("unhandled exception", exc_info=error)
    return _envelope(500, AppError.code, "Internal server error", {})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(OperationalError, _handle_database_down)
    app.add_exception_handler(Exception, _handle_unexpected)
