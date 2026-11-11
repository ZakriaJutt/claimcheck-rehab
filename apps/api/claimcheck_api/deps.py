"""Request dependencies: principal from the session cookie, CSRF check on writes, today's date."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy import Engine, text

from claimcheck_core.auth.service import token_hash
from claimcheck_core.dates import local_today
from claimcheck_core.db import get_engine
from claimcheck_core.settings import get_settings
from claimcheck_core.tenancy import system_session


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    clinic_id: uuid.UUID
    role: str


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str, fields: list[dict[str, Any]] | None = None) -> None:
        super().__init__(status_code=status, detail=message)
        self.code = code
        self.fields = fields


def engine_dep() -> Engine:
    return get_engine()


def today_dep() -> date:
    return local_today()


CSRF_COOKIE = "cc_csrf"
PENDING_COOKIE = "cc_pending"


def hash_token(token: str) -> str:
    return token_hash(token)


def check_csrf(request: Request) -> None:
    """Anti-forgery on every write (ASVS 3.5.1): a present Origin must be ours, and the double-submit
    token in the X-CSRF-Token header must equal the cc_csrf cookie (SameSite=Strict)."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    origin = request.headers.get("Origin")
    if origin is not None and origin.rstrip("/") != get_settings().public_base_url:
        raise ApiError(403, "csrf", "Reload the page and try again.")
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get("X-CSRF-Token")
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise ApiError(403, "csrf", "Reload the page and try again.")


def client_ip(request: Request) -> str:
    # Direct peer address. Behind the production proxy (Caddy) this must read the proxy's forwarded
    # address instead; recorded as open in the TRD.
    return request.client.host if request.client else "unknown"


def principal_dep(request: Request, engine: Engine = Depends(engine_dep)) -> Principal:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise ApiError(401, "unauthenticated", "Sign in again.")
    with system_session(engine) as s:
        row = s.execute(text("SELECT * FROM cc_session_principal(:h, :m)"),
                        {"h": hash_token(token), "m": settings.session_idle_minutes}).mappings().first()
    if row is None:
        raise ApiError(401, "unauthenticated", "Sign in again.")
    if row["clinic_id"] is None or row["role"] not in ("owner", "staff"):
        raise ApiError(403, "forbidden", "This page is for clinic users.")
    check_csrf(request)
    return Principal(row["user_id"], row["clinic_id"], row["role"])


def owner_dep(p: Principal = Depends(principal_dep)) -> Principal:
    if p.role != "owner":
        raise ApiError(403, "forbidden", "Only the clinic owner can see this.")
    return p
