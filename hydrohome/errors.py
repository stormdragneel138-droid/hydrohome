"""Custom exceptions so every layer can fail in a predictable, catchable way."""


class AppError(Exception):
    """Base class for all expected (user-facing) application errors."""


class ValidationError(AppError):
    """One or more form fields are invalid. `.errors` holds every message."""

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


class DatabaseError(AppError):
    """Wraps sqlite3 errors so the UI never sees low-level exceptions."""


class FileServiceError(AppError):
    """Missing file, bad format, or permission problem."""


class WeatherError(AppError):
    """HTTP, connection, timeout, or malformed-response problem with the API."""


class MeterSyncError(AppError):
    """Smart-meter source unreachable, misconfigured, or returned unusable data."""


# ---- Web/REST API errors (added for the FastAPI layer) -----------------------
class NotFoundError(AppError):
    """The requested record does not exist (HTTP 404)."""


class ConflictError(AppError):
    """The request conflicts with existing data (HTTP 409)."""


class AuthError(AppError):
    """Missing, invalid, or expired credentials (HTTP 401)."""
