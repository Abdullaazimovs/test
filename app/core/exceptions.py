"""Domain-level exceptions and their HTTP mapping.

Services raise framework-agnostic ``AppError`` subclasses; a single exception
handler (registered in ``app.main``) translates them into JSON responses. This
keeps the business layer decoupled from FastAPI/HTTP concerns and makes the API
error format consistent.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class for expected, client-facing errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = "Bad request"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "Resource already exists"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Could not authenticate"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Not enough permissions"


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Validation failed"


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """Render any :class:`AppError` as ``{"detail": ...}``."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
