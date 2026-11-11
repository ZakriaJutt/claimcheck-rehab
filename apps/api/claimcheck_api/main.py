"""App factory: correlation IDs, one error shape {code, message, correlation_id, fields?}, health checks."""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from claimcheck_api.auth_routes import router as auth_router
from claimcheck_api.deps import ApiError
from claimcheck_api.routes import router
from claimcheck_core import logging as cclog
from claimcheck_core.db import get_engine
from claimcheck_core.migrations_info import head_revision
from claimcheck_core.settings import get_settings

_UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")
_log = cclog.get_logger("api")


def _error(status: int, code: str, message: str, fields: object = None) -> JSONResponse:
    body: dict[str, object] = {"code": code, "message": message, "correlation_id": cclog.get_correlation_id()}
    if fields is not None:
        body["fields"] = fields
    return JSONResponse(status_code=status, content=body)


def create_app() -> FastAPI:
    settings = get_settings()  # fails fast, naming any missing variable (UT-14)
    cclog.configure(settings.log_level)
    app = FastAPI(title="ClaimCheck Rehab API", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def correlation(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get("X-Correlation-ID", "")
        cid = incoming if _UUID_RE.match(incoming) else str(uuid.uuid4())
        token = cclog.set_correlation_id(cid)
        try:
            response = await call_next(request)
        finally:
            cclog.reset_correlation_id(token)
        response.headers["X-Correlation-ID"] = cid
        # B2 security headers: no sniffing, no framing, no referrer, nothing from the API cached.
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if settings.cookie_secure and settings.app_env in ("staging", "production"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError) -> JSONResponse:
        resp = _error(exc.status_code, exc.code, str(exc.detail), exc.fields)
        if exc.headers:
            resp.headers.update(exc.headers)
        return resp

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Field locations only; FastAPI's default would echo the submitted values.
        fields = [{"field": ".".join(str(p) for p in e.get("loc", ()) if p != "body"), "code": e.get("type")}
                  for e in exc.errors()]
        return _error(422, "invalid_request", "The request is not in the expected shape.", fields)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        cclog.log_event(_log, "unhandled_error", 40, error_type=type(exc).__name__)
        return _error(500, "internal_error", "Something went wrong. Quote the correlation ID.")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        try:
            with get_engine().connect() as conn:
                current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        except Exception:  # noqa: BLE001
            return _error(503, "database_unavailable", "Database not reachable.")
        if current != head_revision():
            return _error(503, "migration_not_at_head", "Database schema is not at the expected revision.")
        return JSONResponse({"status": "ready", "migration": current})

    app.include_router(router)
    app.include_router(auth_router)
    return app
