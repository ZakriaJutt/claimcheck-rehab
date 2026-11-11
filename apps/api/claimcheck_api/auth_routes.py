"""B2 sign-in, invitations, password reset and users (TRD API table). Every write checks anti-forgery
(Origin and double-submit token); sign-in, second factor, reset and invitation acceptance are rate-limited.
"""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, select

from claimcheck_api.deps import (
    CSRF_COOKIE,
    PENDING_COOKIE,
    ApiError,
    Principal,
    check_csrf,
    client_ip,
    csrf_for_session,
    engine_dep,
    owner_dep,
    principal_dep,
)
from claimcheck_core.audit import write_audit
from claimcheck_core.auth import service
from claimcheck_core.mail import get_mailer, invite_mail, reset_mail, send_safely
from claimcheck_core.models import AppUser
from claimcheck_core.settings import get_settings
from claimcheck_core.tenancy import tenant_session

router = APIRouter(prefix="/api/v1")
EMAIL = r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}$"
TOKEN_PATTERN = r"^[A-Za-z0-9_-]{20,128}$"  # noqa: S105 - a regular expression, not a secret


class SignInIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    email: str = Field(pattern=EMAIL, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class MfaIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: str | None = Field(default=None, pattern=r"^[0-9 ]{6,8}$")
    recovery_code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9 -]{24,40}$")


class EmailIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    email: str = Field(pattern=EMAIL, max_length=254)


class TokenPasswordIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    token: str = Field(pattern=TOKEN_PATTERN)
    password: str = Field(min_length=1, max_length=1024)


class InviteIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    email: str = Field(pattern=EMAIL, max_length=254)
    role: str = Field(pattern=r"^(owner|staff)$")


def _cookie(response: Response, name: str, value: str, *, http_only: bool, same_site: str, path: str = "/",
            max_age: int | None = None) -> None:
    response.set_cookie(name, value, max_age=max_age, path=path, secure=get_settings().cookie_secure,
                        httponly=http_only, samesite=same_site)  # type: ignore[arg-type]


def _set_csrf(response: Response, session_token: str | None = None) -> str:
    """Bound to the session when there is one (B2-S03); otherwise a random double-submit value."""
    token = csrf_for_session(session_token) if session_token else secrets.token_urlsafe(32)
    _cookie(response, CSRF_COOKIE, token, http_only=False, same_site="strict")
    return token


def _rate_limited() -> ApiError:
    err = ApiError(429, "rate_limited", "Too many attempts. Wait 15 minutes and try again.")
    err.headers = {"Retry-After": str(get_settings().rate_window_seconds)}
    return err


def _clear_pending(response: Response) -> None:
    response.delete_cookie(PENDING_COOKIE, path="/api/v1/auth", secure=get_settings().cookie_secure,
                           httponly=True, samesite="strict")


@router.get("/auth/csrf")
def get_csrf(request: Request, response: Response) -> dict[str, str]:
    """Issues the anti-forgery token before the first write (sign-in included, against login CSRF); with a
    session cookie, the token of that session."""
    return {"csrf": _set_csrf(response, request.cookies.get(get_settings().session_cookie_name))}


@router.post("/auth/sign-in")
def post_sign_in(body: SignInIn, request: Request, response: Response,
                 engine: Engine = Depends(engine_dep)) -> dict[str, Any]:
    check_csrf(request)
    r = service.sign_in(engine, body.email, body.password, client_ip(request))
    if r.outcome == "rate_limited":
        raise _rate_limited()
    if r.outcome != "pending" or r.pending_token is None:
        raise ApiError(401, "bad_credentials", "The email or password is not right.")
    _cookie(response, PENDING_COOKIE, r.pending_token, http_only=True, same_site="strict", path="/api/v1/auth",
            max_age=get_settings().mfa_pending_minutes * 60)
    return {"next": r.next_step}


def _pending_token(request: Request) -> str:
    token = request.cookies.get(PENDING_COOKIE)
    if not token:
        raise ApiError(401, "sign_in_expired", "Sign in again.")
    return token


@router.post("/auth/totp/enrol")
def post_totp_enrol(request: Request, engine: Engine = Depends(engine_dep)) -> dict[str, str]:
    check_csrf(request)
    token = _pending_token(request)
    p = service.pending(engine, token)
    if p is None:
        raise ApiError(401, "sign_in_expired", "Sign in again.")
    out = service.enrol_totp(engine, token, f"user-{str(p.user_id)[:8]}")
    if out is None:
        raise ApiError(409, "already_enrolled", "Your authenticator app is already set up. Enter its code.")
    return {"secret": out[0], "otpauth_uri": out[1]}


@router.post("/auth/mfa")
def post_mfa(body: MfaIn, request: Request, response: Response,
             engine: Engine = Depends(engine_dep)) -> dict[str, Any]:
    """Second factor: a TOTP code (also confirms a new enrolment) or one recovery code."""
    check_csrf(request)
    r = service.complete_mfa(engine, _pending_token(request), body.code, body.recovery_code)
    if r.outcome == "rate_limited":
        raise _rate_limited()
    if r.outcome == "expired":
        raise ApiError(401, "sign_in_expired", "Sign in again.")
    if r.outcome != "signed_in" or r.session_token is None:
        raise ApiError(401, "bad_code", "That code is not right. Use the current code from your app.")
    _cookie(response, get_settings().session_cookie_name, r.session_token, http_only=True, same_site="lax")
    _clear_pending(response)
    csrf = _set_csrf(response, r.session_token)  # the new session's own anti-forgery token
    out: dict[str, Any] = {"role": r.role, "csrf": csrf}
    if r.recovery_codes:
        out["recovery_codes"] = r.recovery_codes
    return out


@router.post("/auth/sign-out", status_code=204)
def post_sign_out(request: Request, response: Response, engine: Engine = Depends(engine_dep)) -> Response:
    name = get_settings().session_cookie_name
    token = request.cookies.get(name)
    # A live session is signed out only with its own anti-forgery token; a dead one with the plain pair.
    check_csrf(request, bind=token is not None and service.session_is_live(engine, token))
    if token:
        service.sign_out(engine, token)
    pending = request.cookies.get(PENDING_COOKIE)
    if pending:
        service.sign_out(engine, pending)
    out = Response(status_code=204)
    secure = get_settings().cookie_secure
    out.delete_cookie(name, path="/", secure=secure, httponly=True, samesite="lax")
    out.delete_cookie(CSRF_COOKIE, path="/", secure=secure, samesite="strict")
    _clear_pending(out)
    return out


@router.get("/auth/me")
def get_me(p: Principal = Depends(principal_dep)) -> dict[str, str]:
    return {"user_id": str(p.user_id), "clinic_id": str(p.clinic_id), "role": p.role}


RESET_ANSWER = {"message": "If this address has an account, we have sent it a link."}


def _send_reset(engine: Engine, email: str) -> None:
    out = service.issue_reset(engine, email)
    if out is not None:
        send_safely(get_mailer(), reset_mail(out[0], out[1], get_settings().reset_minutes), "password_reset")


@router.post("/auth/reset-request", status_code=202)
def post_reset_request(body: EmailIn, request: Request, background: BackgroundTasks,
                       engine: Engine = Depends(engine_dep)) -> dict[str, str]:
    """The same answer, and the same work before answering, whether or not the address exists (B2-S06):
    the lookup, the reset row and the email run after the response is sent."""
    check_csrf(request)
    if service.reset_allowed(engine, body.email, client_ip(request)):
        background.add_task(_send_reset, engine, body.email)
    return RESET_ANSWER  # also when rate-limited


@router.post("/auth/reset")
def post_reset(body: TokenPasswordIn, request: Request, engine: Engine = Depends(engine_dep)) -> dict[str, str]:
    check_csrf(request)
    outcome, problem = service.complete_reset(engine, body.token, body.password, client_ip(request))
    if outcome == "rate_limited":
        raise _rate_limited()
    if outcome == "weak_password":
        raise ApiError(422, "weak_password", "Choose a longer or less common password.",
                       [{"field": "password", "code": problem}])
    if outcome != "reset":
        raise ApiError(400, "link_not_valid", "This link has expired or was already used. Ask for a new one.")
    return {"next": "sign_in"}


# ---------------------------------------------------------------- invitations and users


@router.post("/invites", status_code=201)
def post_invite(body: InviteIn, p: Principal = Depends(owner_dep),
                engine: Engine = Depends(engine_dep)) -> dict[str, Any]:
    invite_id, token, expires = service.create_invite(engine, p.clinic_id, body.email, body.role, p.user_id)
    sent = send_safely(get_mailer(), invite_mail(body.email, token, get_settings().invite_hours), "invite")
    return {"id": str(invite_id), "expires_at": expires.isoformat(), "email_sent": sent}


@router.post("/invites/accept")
def post_invite_accept(body: TokenPasswordIn, request: Request, response: Response,
                       engine: Engine = Depends(engine_dep)) -> dict[str, Any]:
    """Token in the body, not the path, so it does not appear in access logs (TRD lists the path form)."""
    check_csrf(request)
    outcome, pending, problem = service.accept_invite(engine, body.token, body.password, client_ip(request))
    if outcome == "rate_limited":
        raise _rate_limited()
    if outcome == "weak_password":
        raise ApiError(422, "weak_password", "Choose a longer or less common password.",
                       [{"field": "password", "code": problem}])
    if outcome == "email_taken":
        raise ApiError(409, "email_taken", "This address already has an account. Ask your clinic owner.")
    if outcome != "accepted" or pending is None:
        raise ApiError(400, "link_not_valid", "This invitation has expired or was already used. Ask for a new one.")
    _cookie(response, PENDING_COOKIE, pending, http_only=True, same_site="strict", path="/api/v1/auth",
            max_age=get_settings().mfa_pending_minutes * 60)
    return {"next": "enrol"}


@router.get("/users")
def get_users(p: Principal = Depends(owner_dep), engine: Engine = Depends(engine_dep)) -> dict[str, Any]:
    with tenant_session(engine, p.clinic_id) as s:
        users = [{"id": str(u.id), "email": u.email, "role": u.role, "removed": u.disabled_at is not None}
                 for u in s.scalars(select(AppUser).order_by(AppUser.created_at))]
    return {"users": users}


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: uuid.UUID, request: Request, p: Principal = Depends(owner_dep),
                engine: Engine = Depends(engine_dep)) -> Response:
    if user_id == p.user_id:
        raise ApiError(409, "cannot_remove_self", "You cannot remove yourself.")
    token = request.cookies.get(get_settings().session_cookie_name) or ""
    if not service.disable_user(engine, token, user_id):
        # Another clinic's user, or one already removed: not found (MH-10 c).
        with tenant_session(engine, p.clinic_id) as s:
            exists = s.get(AppUser, user_id) is not None
            if not exists:
                write_audit(s, "cross_clinic_denied", "not_found", p.clinic_id, p.user_id, "app_user", user_id)
        raise ApiError(404, "not_found", "Not found.")
    service.audit(engine, "user_removed", "ok", p.clinic_id, p.user_id, {"sessions_ended": True})
    return Response(status_code=204)
