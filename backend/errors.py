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


class InvalidSearchError(AppError):
    status_code = 422
    code = "invalid_search"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"


class IngestError(AppError):
    code = "ingest_failed"


def invalid_search_error(message: str, error: ValidationError) -> InvalidSearchError:
    """A pydantic ValidationError raised while building a SearchIntent from
    user-supplied input (query params, free-text query) is a 422, not a 500.
    Only call this at an actual user-input boundary — not for a corrupted cache
    payload, which must stay a 500."""
    details = error.errors(include_url=False, include_context=False)
    return InvalidSearchError(message, {"errors": details})


def _envelope(status_code: int, code: str, message: str, details: Any) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details}}
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


async def _handle_app_error(_: Request, error: AppError) -> JSONResponse:
    return _envelope(error.status_code, error.code, error.message, error.context)


async def _handle_validation_error(
    _: Request, error: RequestValidationError
) -> JSONResponse:
    return _envelope(422, "validation_error", "Invalid request", error.errors())


async def _handle_http_error(_: Request, error: StarletteHTTPException) -> JSONResponse:
    return _envelope(error.status_code, "http_error", str(error.detail), {})


async def _handle_database_down(_: Request, error: OperationalError) -> JSONResponse:
    logger.error("database unavailable", exc_info=error)
    unavailable = ServiceUnavailableError("Database unavailable")
    return _envelope(unavailable.status_code, unavailable.code, unavailable.message, {})


async def _handle_unexpected(_: Request, error: Exception) -> JSONResponse:
    logger.error("unhandled exception", exc_info=error)
    return _envelope(500, AppError.code, "Internal server error", {})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(OperationalError, _handle_database_down)
    app.add_exception_handler(Exception, _handle_unexpected)
