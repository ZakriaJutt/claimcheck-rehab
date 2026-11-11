"""Sign-in service (B2) over the `cc_auth_*` database functions (owned by `claimcheck_auth_owner`).

Flow (TRD Identity and tenancy): email and password open a *pending* sign-in (a session row with
`mfa_passed = false`, 5 minutes, its own cookie, accepted by no data endpoint); a TOTP code or a recovery
code completes it, revokes the pending row and opens a full session under a new token (rotation). A user
whose authenticator is not yet confirmed enrols it first; the confirming code completes sign-in and the
ten recovery codes are shown once. Email is never an authentication factor: it carries invitations and
reset links, and a reset ends every session and does not sign the user in.

Tokens: 256 bits from `secrets`, stored only as SHA-256. Rate limits: fixed windows in `auth_attempt`,
keyed by a hash of the account or of the client address.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import Engine, select, text

from claimcheck_core.audit import write_audit, write_global_audit
from claimcheck_core.auth import passwords, totp
from claimcheck_core.models import Invite
from claimcheck_core.settings import get_settings
from claimcheck_core.tenancy import system_session, tenant_session


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _bucket(kind: str, value: str) -> str:
    return f"{kind}:{hashlib.sha256(value.strip().lower().encode()).hexdigest()[:32]}"


def rate_ok(engine: Engine, kind: str, value: str, limit: int) -> bool:
    """Records an attempt and says whether the bucket is within its limit (every attempt counts)."""
    window = get_settings().rate_window_seconds
    with system_session(engine) as s:
        return bool(s.execute(text("SELECT cc_auth_rate_hit(:b, :w, :m)"),
                              {"b": _bucket(kind, value), "w": window, "m": limit}).scalar())


def rate_reserve(engine: Engine, kind: str, value: str, limit: int) -> uuid.UUID | None:
    """Failures-only limits (B2-S01): in one database statement, before verifying, count the bucket and
    take a slot if one is free. Parallel requests cannot all pass: at most `limit` are ever evaluated per
    window. None means refused. A success gives the slot back with `rate_release`."""
    window = get_settings().rate_window_seconds
    with system_session(engine) as s:
        v = s.execute(text("SELECT cc_auth_rate_reserve(:b, :w, :m)"),
                      {"b": _bucket(kind, value), "w": window, "m": limit}).scalar()
    return v if isinstance(v, uuid.UUID) else (uuid.UUID(str(v)) if v else None)


def rate_release(engine: Engine, slot: uuid.UUID) -> None:
    with system_session(engine) as s:
        s.execute(text("SELECT cc_auth_rate_release(:i)"), {"i": slot})


def audit(engine: Engine, action: str, outcome: str, clinic_id: uuid.UUID | None, user_id: uuid.UUID | None,
          meta: dict[str, object] | None = None) -> None:
    if clinic_id is None:
        with system_session(engine) as s:
            write_global_audit(s, action, outcome, user_id, meta)
    else:
        with tenant_session(engine, clinic_id) as s:
            write_audit(s, action, outcome, clinic_id, user_id, "app_user", user_id, meta)


# ---------------------------------------------------------------- password step


@dataclass(frozen=True)
class SignIn:
    outcome: Literal["pending", "bad_credentials", "rate_limited"]
    pending_token: str | None = None
    next_step: Literal["mfa", "enrol"] | None = None


def sign_in(engine: Engine, email: str, password: str, client_ip: str) -> SignIn:
    st = get_settings()
    # The address limit counts every attempt; the account limit counts failures only (a slot is taken
    # before verifying and given back on success), so a user who signs in often is not locked out, while
    # guessing one account stops after the limit however many requests run in parallel.
    ip_ok = rate_ok(engine, "signin:ip", client_ip, st.rate_signin_per_ip)
    slot = rate_reserve(engine, "signin:acct", email, st.rate_signin_per_account) if ip_ok else None
    if slot is None:
        audit(engine, "sign_in", "rate_limited", None, None, {"limit": "ip" if not ip_ok else "account"})
        return SignIn("rate_limited")
    with system_session(engine) as s:
        row = s.execute(text("SELECT * FROM cc_auth_lookup(:e)"), {"e": email.strip()}).mappings().first()
    ok = passwords.verify_password(row["password_hash"] if row else None, password)
    if row is None or not ok or row["disabled"] or row["clinic_id"] is None:
        # Operators do not sign in through the clinic path in B2 (operator screens are not built).
        # The slot stays taken: this failure counts.
        audit(engine, "sign_in", "failed", row["clinic_id"] if row else None, row["user_id"] if row else None)
        return SignIn("bad_credentials")
    rate_release(engine, slot)
    pending = new_token()
    with system_session(engine) as s:
        s.execute(text("SELECT cc_auth_session_open(:u, :h, false, :m)"),
                  {"u": row["user_id"], "h": token_hash(pending), "m": st.mfa_pending_minutes})
    audit(engine, "sign_in_password", "ok", row["clinic_id"], row["user_id"])
    return SignIn("pending", pending, "mfa" if row["totp_confirmed"] else "enrol")


# ---------------------------------------------------------------- second factor


@dataclass(frozen=True)
class Pending:
    user_id: uuid.UUID
    clinic_id: uuid.UUID
    role: str
    secret_enc: bytes | None
    totp_confirmed: bool
    last_used_step: int | None


def pending(engine: Engine, pending_token: str) -> Pending | None:
    with system_session(engine) as s:
        r = s.execute(text("SELECT * FROM cc_auth_pending(:h)"), {"h": token_hash(pending_token)}).mappings().first()
    if r is None or r["clinic_id"] is None:
        return None
    return Pending(r["user_id"], r["clinic_id"], r["role"], bytes(r["secret_enc"]) if r["secret_enc"] else None,
                   bool(r["totp_confirmed"]), r["last_used_step"])


def enrol_totp(engine: Engine, pending_token: str, account_label: str) -> tuple[str, str] | None:
    """A new secret for a user whose authenticator is not confirmed. Returns (base32 secret, otpauth URI)."""
    p = pending(engine, pending_token)
    if p is None or p.totp_confirmed:
        return None
    secret = totp.new_secret()
    sealed = totp.SecretBox(get_settings().totp_encryption_key).seal(secret)
    with system_session(engine) as s:
        stored = s.execute(text("SELECT cc_auth_totp_enrol(:h, :s)"),
                           {"h": token_hash(pending_token), "s": sealed}).scalar()
    if not stored:
        return None
    audit(engine, "mfa_enrol_started", "ok", p.clinic_id, p.user_id)
    return totp.b32(secret), totp.otpauth_uri(secret, account_label)


@dataclass(frozen=True)
class MfaResult:
    outcome: Literal["signed_in", "invalid", "rate_limited", "expired"]
    session_token: str | None = None
    user_id: uuid.UUID | None = None
    clinic_id: uuid.UUID | None = None
    role: str | None = None
    recovery_codes: list[str] | None = None


def complete_mfa(engine: Engine, pending_token: str, code: str | None = None, recovery_code: str | None = None,
                 now: float | None = None) -> MfaResult:
    st = get_settings()
    p = pending(engine, pending_token)
    if p is None:
        return MfaResult("expired")
    slot = rate_reserve(engine, "mfa:user", str(p.user_id), st.rate_mfa_per_user)
    if slot is None:
        audit(engine, "sign_in_mfa", "rate_limited", p.clinic_id, p.user_id)
        return MfaResult("rate_limited")
    if (code is None) == (recovery_code is None) or p.secret_enc is None:
        return MfaResult("invalid")
    step: int | None = None
    rhash: str | None = None
    if code is not None:
        secret = totp.SecretBox(st.totp_encryption_key).open(p.secret_enc)
        step = totp.match_step(secret, code, now, p.last_used_step)
        if step is None:
            audit(engine, "sign_in_mfa", "failed", p.clinic_id, p.user_id, {"factor": "totp"})
            return MfaResult("invalid")
    else:
        if not p.totp_confirmed or recovery_code is None:
            return MfaResult("invalid")
        rhash = totp.recovery_hash(recovery_code)
    session_token = new_token()
    with system_session(engine) as s:
        user = s.execute(text("SELECT cc_auth_mfa_complete(:p, :n, :st, :rc, :m)"),
                         {"p": token_hash(pending_token), "n": token_hash(session_token), "st": step, "rc": rhash,
                          "m": st.session_absolute_minutes}).scalar()
    if user is None:
        audit(engine, "sign_in_mfa", "failed", p.clinic_id, p.user_id,
              {"factor": "totp" if code is not None else "recovery_code", "reason": "replay_or_used"})
        return MfaResult("invalid")
    rate_release(engine, slot)
    codes: list[str] | None = None
    if not p.totp_confirmed:  # first confirmation: issue recovery codes, shown once
        codes = totp.new_recovery_codes()
        with system_session(engine) as s:
            s.execute(text("SELECT cc_auth_recovery_set(:h, :c)"),
                      {"h": token_hash(session_token), "c": [totp.recovery_hash(c) for c in codes]})
        audit(engine, "mfa_enrolled", "ok", p.clinic_id, p.user_id)
    audit(engine, "sign_in", "ok", p.clinic_id, p.user_id,
          {"factor": "totp" if code is not None else "recovery_code"})
    return MfaResult("signed_in", session_token, p.user_id, p.clinic_id, p.role, codes)


def session_is_live(engine: Engine, token: str) -> bool:
    with system_session(engine) as s:
        return s.execute(text("SELECT 1 FROM cc_session_principal(:h, :m)"),
                         {"h": token_hash(token), "m": get_settings().session_idle_minutes}).first() is not None


def sign_out(engine: Engine, token: str) -> int:
    with system_session(engine) as s:
        return int(s.execute(text("SELECT cc_auth_session_revoke(:h)"), {"h": token_hash(token)}).scalar() or 0)


# ---------------------------------------------------------------- reset


def reset_allowed(engine: Engine, email: str, client_ip: str) -> bool:
    """The request-time part of a reset request: the same two limit calls for every address."""
    st = get_settings()
    ok = (rate_ok(engine, "reset:ip", client_ip, st.rate_public_per_ip)
          and rate_ok(engine, "reset:acct", email, st.rate_reset_per_account))
    if not ok:
        audit(engine, "password_reset_request", "rate_limited", None, None)
    return ok


def issue_reset(engine: Engine, email: str) -> tuple[str, str] | None:
    """Runs after the response has been sent (B2-S06), so whether the address exists does not change the
    response time. Returns (address, token) to email, or None."""
    st = get_settings()
    with system_session(engine) as s:
        row = s.execute(text("SELECT * FROM cc_auth_lookup(:e)"), {"e": email.strip()}).mappings().first()
    if row is None or row["disabled"] or row["clinic_id"] is None:
        return None
    token = new_token()
    with system_session(engine) as s:
        s.execute(text("SELECT cc_auth_reset_create(:u, :h, :m)"),
                  {"u": row["user_id"], "h": token_hash(token), "m": st.reset_minutes})
    audit(engine, "password_reset_request", "ok", row["clinic_id"], row["user_id"])
    return email.strip(), token


ResetOutcome = Literal["reset", "invalid", "used", "expired", "weak_password", "rate_limited"]


def complete_reset(engine: Engine, token: str, new_password: str, client_ip: str) -> tuple[ResetOutcome, str | None]:
    if not rate_ok(engine, "public:ip", client_ip, get_settings().rate_public_per_ip):
        return "rate_limited", None
    problem = passwords.policy_problem(new_password)
    if problem:
        return "weak_password", problem
    with system_session(engine) as s:
        r = s.execute(text("SELECT * FROM cc_auth_reset_complete(:h, :p)"),
                      {"h": token_hash(token), "p": passwords.hash_password(new_password)}).mappings().one()
    audit(engine, "password_reset", r["outcome"], r["clinic_id"], r["user_id"])
    return r["outcome"], None


# ---------------------------------------------------------------- invitations


def create_invite(engine: Engine, clinic_id: uuid.UUID, email: str, role: str,
                  invited_by: uuid.UUID | None) -> tuple[uuid.UUID, str, datetime]:
    """Owner (or the operator script for a clinic's first owner). A new invitation to the same address
    replaces the pending one. Returns (invite id, token to email, expiry)."""
    if role not in ("owner", "staff"):
        raise ValueError("role")
    token = new_token()
    expires = datetime.now(tz=UTC) + timedelta(hours=get_settings().invite_hours)
    with tenant_session(engine, clinic_id) as s:
        inv = s.scalars(select(Invite).where(Invite.email == email.strip(), Invite.accepted_at.is_(None))
                        .with_for_update()).first()
        if inv is None:
            inv = Invite(clinic_id=clinic_id, email=email.strip(), role=role, token_hash=token_hash(token),
                         expires_at=expires, invited_by=invited_by)
            s.add(inv)
        else:
            inv.role, inv.token_hash, inv.expires_at, inv.invited_by = role, token_hash(token), expires, invited_by
        s.flush()
        write_audit(s, "invite_created", "ok", clinic_id, invited_by, "invite", inv.id, {"role": role})
        return inv.id, token, expires


InviteOutcome = Literal["accepted", "invalid", "used", "expired", "email_taken", "weak_password", "rate_limited"]


def accept_invite(engine: Engine, token: str, password: str, client_ip: str
                  ) -> tuple[InviteOutcome, str | None, str | None]:
    """Returns (outcome, pending sign-in token for enrolment, password problem code)."""
    st = get_settings()
    if not rate_ok(engine, "public:ip", client_ip, st.rate_public_per_ip):
        return "rate_limited", None, None
    problem = passwords.policy_problem(password)
    if problem:
        return "weak_password", None, problem
    with system_session(engine) as s:
        r = s.execute(text("SELECT * FROM cc_auth_invite_accept(:h, :p)"),
                      {"h": token_hash(token), "p": passwords.hash_password(password)}).mappings().one()
    audit(engine, "invite_accept", r["outcome"], r["clinic_id"], r["user_id"])
    if r["outcome"] != "accepted":
        return r["outcome"], None, None
    pending_token = new_token()
    with system_session(engine) as s:
        s.execute(text("SELECT cc_auth_session_open(:u, :h, false, :m)"),
                  {"u": r["user_id"], "h": token_hash(pending_token), "m": st.mfa_pending_minutes})
    return "accepted", pending_token, None


def disable_user(engine: Engine, actor_session_token: str, target: uuid.UUID) -> bool:
    with system_session(engine) as s:
        n = s.execute(text("SELECT cc_auth_user_disable(:a, :t, :m)"),
                      {"a": token_hash(actor_session_token), "t": target,
                       "m": get_settings().session_idle_minutes}).scalar()
    return bool(n)
