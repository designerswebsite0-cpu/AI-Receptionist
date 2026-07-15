from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for domain errors that map to the api.md error envelope."""

    code = "APP_ERROR"
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    status_code = status.HTTP_403_FORBIDDEN


class UnauthorizedError(AppError):
    code = "UNAUTHORIZED"
    status_code = status.HTTP_401_UNAUTHORIZED


class ConflictError(AppError):
    code = "CONFLICT"
    status_code = status.HTTP_409_CONFLICT


class ValidationErrorApp(AppError):
    """A business-rule validation failure (distinct from Pydantic's
    RequestValidationError, which is handled separately below)."""

    code = "VALIDATION_ERROR"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class RateLimitedError(AppError):
    code = "RATE_LIMITED"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


def _error_envelope(code: str, message: str) -> dict:
    return {"success": False, "error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_envelope(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_envelope("VALIDATION_ERROR", "Request validation failed"),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_envelope("HTTP_ERROR", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception processing %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_envelope("INTERNAL_ERROR", "An unexpected error occurred"),
        )
