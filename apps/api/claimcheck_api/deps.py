"""Request dependencies: principal from the session cookie, CSRF check on writes, today's date."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
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


def csrf_for_session(session_token: str) -> str:
    """The anti-forgery token of one session (B2-S03): HMAC-SHA-256 of the session token under a key
    derived from TOTP_ENCRYPTION_KEY with its own label. Another session's pair never matches."""
    key = hmac.new(base64.b64decode(get_settings().totp_encryption_key), b"claimcheck-csrf-v1",
                   hashlib.sha256).digest()
    mac = hmac.new(key, session_token.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def check_csrf(request: Request, bind: bool = False) -> None:
    """Anti-forgery on every write (ASVS 3.5.1): a present Origin must be ours. On a write made with a live
    session (`bind=True`: every endpoint behind `principal_dep`, and sign-out of a live session) the
    X-CSRF-Token header must be that session's own token (`csrf_for_session`, B2-S03). On the
    pre-authentication endpoints (sign-in, second factor, reset, invitation), which act with no session's
    authority, it must equal the cc_csrf cookie (double submit, SameSite=Strict), so a stale session cookie
    left in the browser does not block signing in again."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    origin = request.headers.get("Origin")
    if origin is not None and origin.rstrip("/") != get_settings().public_base_url:
        raise ApiError(403, "csrf", "Reload the page and try again.")
    header = request.headers.get("X-CSRF-Token")
    session_token = request.cookies.get(get_settings().session_cookie_name)
    expected = csrf_for_session(session_token) if bind and session_token else request.cookies.get(CSRF_COOKIE)
    if bind and not session_token:
        expected = None
    if not expected or not header or not secrets.compare_digest(expected, header):
        raise ApiError(403, "csrf", "Reload the page and try again.")


def _trusted(host: str, networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network]) -> bool:
    try:
        addr = ipaddress.ip_address(host.strip())
    except ValueError:
        return False
    return any(addr in n for n in networks)


def client_address(peer: str | None, forwarded_for: list[str], trusted_proxies: str) -> str:
    """The client address for rate limits and audit (review observation S08). The direct TCP peer, unless
    that peer is a configured trusted proxy; then the right-most X-Forwarded-For hop that is not itself a
    trusted proxy. Hops to the left of it are written by the client and never believed."""
    if not peer:
        return "unknown"
    networks = [ipaddress.ip_network(p.strip(), strict=False) for p in trusted_proxies.split(",") if p.strip()]
    if not _trusted(peer, networks):
        return peer
    hops = [h.strip() for value in forwarded_for for h in value.split(",") if h.strip()]
    for hop in reversed(hops):
        if not _trusted(hop, networks):
            return hop
    return hops[0] if hops else peer


def client_ip(request: Request) -> str:
    return client_address(request.client.host if request.client else None,
                          request.headers.getlist("x-forwarded-for"), get_settings().trusted_proxies)


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
    check_csrf(request, bind=True)
    return Principal(row["user_id"], row["clinic_id"], row["role"])


def owner_dep(p: Principal = Depends(principal_dep)) -> Principal:
    if p.role != "owner":
        raise ApiError(403, "forbidden", "Only the clinic owner can see this.")
    return p
