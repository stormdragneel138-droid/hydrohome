"""One consistent JSON error shape for every failure:
{"error": {"code": "validation_error", "message": "...", "details": ["..."]}}"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from hydrohome.errors import (AuthError, ConflictError, DatabaseError, NotFoundError,
                              ValidationError, AppError)


def _body(code, message, details=None):
    return {"error": {"code": code, "message": message, "details": details or []}}


def _friendly(err):
    field = ".".join(str(p) for p in err["loc"] if p not in ("body", "query", "path"))
    return f"{field}: {err['msg']}" if field else err["msg"]


def install_error_handlers(app: FastAPI):
    @app.exception_handler(RequestValidationError)
    async def _request_invalid(_: Request, exc: RequestValidationError):
        details = [_friendly(e) for e in exc.errors()]
        message = details[0] if len(details) == 1 else "Please fix the highlighted problems."
        return JSONResponse(_body("validation_error", message, details), 422)

    @app.exception_handler(ValidationError)
    async def _invalid(_: Request, exc: ValidationError):
        return JSONResponse(_body("validation_error", exc.errors[0] if len(exc.errors) == 1
                                  else "Please fix the highlighted problems.", exc.errors), 422)

    @app.exception_handler(NotFoundError)
    async def _missing(_: Request, exc: NotFoundError):
        return JSONResponse(_body("not_found", str(exc)), 404)

    @app.exception_handler(ConflictError)
    async def _conflict(_: Request, exc: ConflictError):
        return JSONResponse(_body("conflict", str(exc)), 409)

    @app.exception_handler(AuthError)
    async def _auth(_: Request, exc: AuthError):
        return JSONResponse(_body("unauthorized", str(exc)), 401,
                            headers={"WWW-Authenticate": "Bearer"})

    @app.exception_handler(DatabaseError)
    async def _db(_: Request, exc: DatabaseError):
        text = str(exc)
        if "breaks a rule" in text:
            return JSONResponse(_body("conflict", text), 409)
        return JSONResponse(_body("database_error", text), 500)

    @app.exception_handler(AppError)
    async def _app(_: Request, exc: AppError):
        return JSONResponse(_body("bad_request", str(exc)), 400)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(_body(code, str(exc.detail)), exc.status_code)
