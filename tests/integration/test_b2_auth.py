"""B2 sign-in against real PostgreSQL and the local Mailpit inbox (SMTP 127.0.0.1:1025, API :8025).

Invitation by email, password and TOTP enrolment, recovery codes, sign-in, sign-out, expiry, removal,
password reset, refusals of reused and expired links and codes, cross-clinic refusal, rate limits,
anti-forgery and cookie attributes. Every address is synthetic (`@example.test`); every message a test
creates is deleted from Mailpit at the end of the test.
"""

from __future__ import annotations

import base64
import re
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from claimcheck_core.auth import service, totp
from claimcheck_core.mail import SmtpMailer, invite_mail
from claimcheck_core.settings import get_settings
from tests.integration.conftest import TODAY, ClinicCtx, make_clinic

MAILPIT = "http://127.0.0.1:8025/api/v1"
PASSWORD = "tidal-heron-kettle-42"


def _mailpit_up() -> bool:
    try:
        return httpx.get(f"{MAILPIT}/messages", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(not _mailpit_up(), reason="Mailpit not running on 127.0.0.1:8025")


class Inbox:
    def __init__(self) -> None:
        self.ids: list[str] = []

    def wait_for(self, to: str, subject_part: str, timeout: float = 5.0) -> str:
        """The text body of the newest message to `to` whose subject contains `subject_part`."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            r = httpx.get(f"{MAILPIT}/search", params={"query": f'to:"{to}"'}, timeout=5).json()
            for m in r.get("messages", []):
                if subject_part in m["Subject"] and m["ID"] not in self.ids:
                    self.ids.append(m["ID"])
                    return str(httpx.get(f"{MAILPIT}/message/{m['ID']}", timeout=5).json()["Text"])
            time.sleep(0.1)
        raise AssertionError(f"no message for {to}")

    def count(self, to: str) -> int:
        r = httpx.get(f"{MAILPIT}/search", params={"query": f'to:"{to}"'}, timeout=5).json()
        for m in r.get("messages", []):
            if m["ID"] not in self.ids:
                self.ids.append(m["ID"])
        return int(r.get("messages_count", len(r.get("messages", []))))

    def cleanup(self) -> None:
        if self.ids:
            httpx.request("DELETE", f"{MAILPIT}/messages", json={"IDs": self.ids}, timeout=5)


@pytest.fixture
def inbox() -> Iterator[Inbox]:
    box = Inbox()
    yield box
    box.cleanup()


@pytest.fixture
def web(app_engine: Engine) -> Iterator[TestClient]:
    from claimcheck_api.deps import today_dep
    from claimcheck_api.main import create_app
    app = create_app()
    app.dependency_overrides[today_dep] = lambda: TODAY
    with TestClient(app, base_url="https://testserver") as client:  # Secure cookies need https
        yield client


def token_in(body: str) -> str:
    m = re.search(r"#token=([A-Za-z0-9_-]+)", body)
    assert m, "no link in the message"
    assert m.group(0) in body and body.count("http") == 1
    return m.group(1)


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["csrf"]}


def code_for(secret_b32: str, offset: int = 0) -> str:
    secret = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8))
    return totp.code_at(secret, totp.current_step() + offset)


@dataclass
class Account:
    email: str
    secret: str
    recovery_codes: list[str]
    clinic_id: uuid.UUID


def addr(label: str) -> str:
    return f"{label}.{uuid.uuid4().hex[:10]}@example.test"


def invite_by_operator(app_engine: Engine, clinic: ClinicCtx, email: str, role: str = "owner") -> None:
    """The operator path for a clinic's first owner (scripts/invite_owner.py does the same)."""
    _, token, _ = service.create_invite(app_engine, clinic.id, email, role, None)
    SmtpMailer(get_settings()).send(invite_mail(email, token, get_settings().invite_hours))


def accept_and_enrol(client: TestClient, inbox: Inbox, email: str, clinic_id: uuid.UUID) -> Account:
    tok = token_in(inbox.wait_for(email, "invited"))
    h = csrf(client)
    r = client.post("/api/v1/invites/accept", json={"token": tok, "password": PASSWORD}, headers=h)
    assert r.status_code == 200 and r.json() == {"next": "enrol"}, r.text
    assert client.get("/api/v1/auth/me").status_code == 401  # a pending sign-in reaches no data
    r = client.post("/api/v1/auth/totp/enrol", headers=h)
    assert r.status_code == 200, r.text
    secret = r.json()["secret"]
    assert r.json()["otpauth_uri"].startswith("otpauth://totp/") and r.headers["Cache-Control"] == "no-store"
    r = client.post("/api/v1/auth/mfa", json={"code": code_for(secret)}, headers=h)
    assert r.status_code == 200, r.text
    codes = r.json()["recovery_codes"]
    assert len(codes) == 10
    return Account(email, secret, codes, clinic_id)


def sign_in(client: TestClient, acct: Account, offset: int = 1, password: str = PASSWORD) -> httpx.Response:
    client.cookies.clear()
    h = csrf(client)
    r = client.post("/api/v1/auth/sign-in", json={"email": acct.email, "password": password}, headers=h)
    if r.status_code != 200:
        return r
    assert r.json() == {"next": "mfa"}
    return client.post("/api/v1/auth/mfa", json={"code": code_for(acct.secret, offset)}, headers=h)


@pytest.fixture
def owner(web: TestClient, inbox: Inbox, app_engine: Engine, harbourview: ClinicCtx) -> Account:
    email = addr("owner")
    invite_by_operator(app_engine, harbourview, email)
    return accept_and_enrol(web, inbox, email, harbourview.id)


def test_b2_invite_enrol_sign_in_end_to_end_through_mailpit(web: TestClient, inbox: Inbox, owner: Account,
                                                             app_engine: Engine) -> None:
    me = web.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["role"] == "owner" and me.json()["clinic_id"] == str(owner.clinic_id)
    # The owner invites a staff member through the API; the staff member enrols from the emailed link.
    staff_email = addr("staff")
    h = {"X-CSRF-Token": web.cookies.get("cc_csrf") or ""}
    r = web.post("/api/v1/invites", json={"email": staff_email, "role": "staff"}, headers=h)
    assert r.status_code == 201 and r.json()["email_sent"] is True, r.text
    with TestClient(web.app, base_url="https://testserver") as other:
        staff = accept_and_enrol(other, inbox, staff_email, owner.clinic_id)
        assert other.get("/api/v1/auth/me").json()["role"] == "staff"
        assert other.get("/api/v1/users").status_code == 403  # owner-only
    # Signing out ends the session; signing in again needs password and a fresh code.
    assert web.post("/api/v1/auth/sign-out", headers=h).status_code == 204
    assert web.get("/api/v1/auth/me").status_code == 401
    r = sign_in(web, owner)
    assert r.status_code == 200, r.text
    assert "recovery_codes" not in r.json()
    users = web.get("/api/v1/users").json()["users"]
    assert {u["email"] for u in users} >= {owner.email, staff.email}


def test_b2_session_cookie_attributes_and_rotation(web: TestClient, owner: Account) -> None:
    client = web
    client.cookies.clear()
    h = csrf(client)
    r = client.post("/api/v1/auth/sign-in", json={"email": owner.email, "password": PASSWORD}, headers=h)
    pending = r.headers["set-cookie"].lower()
    assert "cc_pending=" in pending and "httponly" in pending and "secure" in pending
    assert "samesite=strict" in pending and "path=/api/v1/auth" in pending
    pending_value = client.cookies.get("cc_pending")
    r = client.post("/api/v1/auth/mfa", json={"code": code_for(owner.secret, 1)}, headers=h)
    cookies = [c.lower() for c in r.headers.get_list("set-cookie")]
    session = next(c for c in cookies if c.startswith("cc_session="))
    assert "httponly" in session and "secure" in session and "samesite=lax" in session and "path=/" in session
    csrf_cookie = next(c for c in cookies if c.startswith("cc_csrf="))
    assert "httponly" not in csrf_cookie and "samesite=strict" in csrf_cookie
    token = client.cookies.get("cc_session")
    assert token and token != pending_value and len(token) >= 43  # 256 bits, new token at sign-in
    # the pending token is spent: it cannot complete a second sign-in
    client.cookies.set("cc_pending", pending_value or "", path="/api/v1/auth")
    h = {"X-CSRF-Token": r.json()["csrf"]}  # the anti-forgery token was renewed with the session
    r = client.post("/api/v1/auth/mfa", json={"code": code_for(owner.secret, 0)}, headers=h)
    assert r.status_code == 401 and r.json()["code"] == "sign_in_expired"
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_b2_reused_and_expired_invitation_links_are_refused(web: TestClient, inbox: Inbox, app_engine: Engine,
                                                            owner_engine: Engine, harbourview: ClinicCtx) -> None:
    email = addr("reuse")
    invite_by_operator(app_engine, harbourview, email, "staff")
    tok = token_in(inbox.wait_for(email, "invited"))
    h = csrf(web)
    assert web.post("/api/v1/invites/accept", json={"token": tok, "password": PASSWORD},
                    headers=h).status_code == 200
    web.cookies.clear()
    h = csrf(web)
    r = web.post("/api/v1/invites/accept", json={"token": tok, "password": PASSWORD}, headers=h)
    assert r.status_code == 400 and r.json()["code"] == "link_not_valid"
    # expired
    email2 = addr("expired")
    invite_by_operator(app_engine, harbourview, email2, "staff")
    tok2 = token_in(inbox.wait_for(email2, "invited"))
    with owner_engine.begin() as c:
        c.execute(text("UPDATE invite SET expires_at = now() - interval '1 second' WHERE email = :e"), {"e": email2})
    r = web.post("/api/v1/invites/accept", json={"token": tok2, "password": PASSWORD}, headers=h)
    assert r.status_code == 400 and r.json()["code"] == "link_not_valid"
    # a common password is refused before the link is spent
    email3 = addr("weak")
    invite_by_operator(app_engine, harbourview, email3, "staff")
    tok3 = token_in(inbox.wait_for(email3, "invited"))
    r = web.post("/api/v1/invites/accept", json={"token": tok3, "password": "password123"}, headers=h)
    assert r.status_code == 422 and r.json()["fields"] == [{"field": "password", "code": "too_common"}]
    assert web.post("/api/v1/invites/accept", json={"token": tok3, "password": PASSWORD},
                    headers=h).status_code == 200


def test_b2_reused_wrong_and_recovery_codes(web: TestClient, owner: Account) -> None:
    # The enrolment used the current step; the same code cannot be used again.
    web.cookies.clear()
    h = csrf(web)
    assert web.post("/api/v1/auth/sign-in", json={"email": owner.email, "password": PASSWORD},
                    headers=h).status_code == 200
    r = web.post("/api/v1/auth/mfa", json={"code": code_for(owner.secret, 0)}, headers=h)
    assert r.status_code == 401 and r.json()["code"] == "bad_code"
    r = web.post("/api/v1/auth/mfa", json={"code": "000000" if code_for(owner.secret, 1) != "000000" else "111111"},
                 headers=h)
    assert r.status_code == 401
    r = web.post("/api/v1/auth/mfa", json={"recovery_code": owner.recovery_codes[0]}, headers=h)
    assert r.status_code == 200, r.text
    # the recovery code is single use
    web.cookies.clear()
    h = csrf(web)
    web.post("/api/v1/auth/sign-in", json={"email": owner.email, "password": PASSWORD}, headers=h)
    r = web.post("/api/v1/auth/mfa", json={"recovery_code": owner.recovery_codes[0]}, headers=h)
    assert r.status_code == 401
    r = web.post("/api/v1/auth/mfa", json={"recovery_code": owner.recovery_codes[1]}, headers=h)
    assert r.status_code == 200


def test_b2_wrong_password_and_unknown_email_look_the_same(web: TestClient, owner: Account) -> None:
    h = csrf(web)
    a = web.post("/api/v1/auth/sign-in", json={"email": owner.email, "password": "wrong-password-1"}, headers=h)
    b = web.post("/api/v1/auth/sign-in", json={"email": addr("nobody"), "password": "wrong-password-1"}, headers=h)
    assert a.status_code == b.status_code == 401
    assert a.json()["message"] == b.json()["message"] and a.json()["code"] == b.json()["code"]


def test_b2_logout_invalidates_the_token_server_side(web: TestClient, owner: Account) -> None:
    token = web.cookies.get("cc_session")
    assert token
    h = {"X-CSRF-Token": web.cookies.get("cc_csrf") or ""}
    assert web.post("/api/v1/auth/sign-out", headers=h).status_code == 204
    web.cookies.clear()
    web.cookies.set("cc_session", token)  # replaying the old cookie after sign-out
    assert web.get("/api/v1/auth/me").status_code == 401
    assert web.get("/api/v1/items").status_code == 401


def test_b2_idle_and_absolute_expiry(web: TestClient, owner: Account, owner_engine: Engine) -> None:
    token = web.cookies.get("cc_session") or ""
    assert web.get("/api/v1/auth/me").status_code == 200
    with owner_engine.begin() as c:
        c.execute(text("UPDATE session SET last_seen_at = now() - interval '31 minutes' WHERE token_hash = :h"),
                  {"h": service.token_hash(token)})
    assert web.get("/api/v1/auth/me").status_code == 401  # idle 30 minutes
    r = sign_in(web, owner)
    assert r.status_code == 200
    token = web.cookies.get("cc_session") or ""
    with owner_engine.begin() as c:
        exp = c.execute(text("SELECT expires_at - created_at FROM session WHERE token_hash = :h"),
                        {"h": service.token_hash(token)}).scalar()
        assert exp is not None and exp.total_seconds() == 12 * 3600  # absolute 12 hours
        c.execute(text("UPDATE session SET expires_at = now() - interval '1 second' WHERE token_hash = :h"),
                  {"h": service.token_hash(token)})
    assert web.get("/api/v1/auth/me").status_code == 401


def test_b2_removed_user_loses_every_session(web: TestClient, inbox: Inbox, owner: Account) -> None:
    staff_email = addr("removed")
    h = {"X-CSRF-Token": web.cookies.get("cc_csrf") or ""}
    assert web.post("/api/v1/invites", json={"email": staff_email, "role": "staff"}, headers=h).status_code == 201
    with TestClient(web.app, base_url="https://testserver") as other:
        accept_and_enrol(other, inbox, staff_email, owner.clinic_id)
        assert other.get("/api/v1/auth/me").status_code == 200
        staff_id = other.get("/api/v1/auth/me").json()["user_id"]
        r = web.delete(f"/api/v1/users/{staff_id}", headers=h)
        assert r.status_code == 204, r.text
        assert other.get("/api/v1/auth/me").status_code == 401
        other.cookies.clear()
        hh = csrf(other)
        r = other.post("/api/v1/auth/sign-in", json={"email": staff_email, "password": PASSWORD}, headers=hh)
        assert r.status_code == 401
    me = web.get("/api/v1/auth/me").json()["user_id"]
    assert web.delete(f"/api/v1/users/{me}", headers=h).status_code == 409


def test_b2_cross_clinic_session_is_refused(web: TestClient, inbox: Inbox, owner: Account, app_engine: Engine,
                                            owner_engine: Engine) -> None:
    other = make_clinic(owner_engine, "Seawall Rehab")
    other_email = addr("seawall")
    invite_by_operator(app_engine, other, other_email)
    with TestClient(web.app, base_url="https://testserver") as b:
        acct_b = accept_and_enrol(b, inbox, other_email, other.id)
        b_user = b.get("/api/v1/auth/me").json()["user_id"]
        hb = {"X-CSRF-Token": b.cookies.get("cc_csrf") or ""}
        r = b.post("/api/v1/imports", json={"export_date": "2026-11-09", "profile_sales_version": 1,
                                            "profile_policies_version": 1},
                   headers={**hb, "Idempotency-Key": "a" * 64})
        b_batch = r.json()["id"]
    assert acct_b.clinic_id != owner.clinic_id
    h = {"X-CSRF-Token": web.cookies.get("cc_csrf") or ""}
    # clinic A's owner session reaches none of clinic B's objects or users
    assert web.get(f"/api/v1/imports/{b_batch}").status_code == 404
    assert web.delete(f"/api/v1/users/{b_user}", headers=h).status_code == 404
    assert all(u["email"] != other_email for u in web.get("/api/v1/users").json()["users"])
    with owner_engine.connect() as c:
        n = c.execute(text("SELECT count(*) FROM audit_event WHERE action = 'cross_clinic_denied' "
                           "AND clinic_id = :c"), {"c": owner.clinic_id}).scalar()
        assert n == 2
        assert c.execute(text("SELECT disabled_at FROM app_user WHERE id = :u"), {"u": b_user}).scalar() is None


def test_b2_password_reset_through_mailpit(web: TestClient, inbox: Inbox, owner: Account,
                                           owner_engine: Engine) -> None:
    old_session = web.cookies.get("cc_session") or ""
    web.cookies.clear()
    h = csrf(web)
    a = web.post("/api/v1/auth/reset-request", json={"email": owner.email}, headers=h)
    nobody = addr("nobody")
    b = web.post("/api/v1/auth/reset-request", json={"email": nobody}, headers=h)
    assert a.status_code == b.status_code == 202 and a.json() == b.json()
    body = inbox.wait_for(owner.email, "Reset")
    tok = token_in(body)
    assert inbox.count(nobody) == 0
    r = web.post("/api/v1/auth/reset", json={"token": tok, "password": "new-" + PASSWORD}, headers=h)
    assert r.status_code == 200 and r.json() == {"next": "sign_in"}
    # every earlier session ended; the reset did not sign anyone in
    web.cookies.set("cc_session", old_session)
    assert web.get("/api/v1/auth/me").status_code == 401
    # reused link refused
    r = web.post("/api/v1/auth/reset", json={"token": tok, "password": "other-" + PASSWORD}, headers=h)
    assert r.status_code == 400 and r.json()["code"] == "link_not_valid"
    # old password refused, new password still needs the second factor
    assert sign_in(web, owner).status_code == 401
    r = sign_in(web, owner, password="new-" + PASSWORD)
    assert r.status_code == 200
    # expired link refused
    web.cookies.clear()
    h = csrf(web)
    web.post("/api/v1/auth/reset-request", json={"email": owner.email}, headers=h)
    tok2 = token_in(inbox.wait_for(owner.email, "Reset"))
    with owner_engine.begin() as c:
        c.execute(text("UPDATE password_reset SET expires_at = now() - interval '1 second' WHERE token_hash = :h"),
                  {"h": service.token_hash(tok2)})
    r = web.post("/api/v1/auth/reset", json={"token": tok2, "password": "third-" + PASSWORD}, headers=h)
    assert r.status_code == 400


def test_b2_sign_in_rate_limit_per_account(web: TestClient, owner: Account) -> None:
    web.cookies.clear()
    h = csrf(web)
    limit = get_settings().rate_signin_per_account
    for _ in range(limit):
        r = web.post("/api/v1/auth/sign-in", json={"email": owner.email, "password": "wrong-password-1"}, headers=h)
        assert r.status_code == 401
    r = web.post("/api/v1/auth/sign-in", json={"email": owner.email, "password": PASSWORD}, headers=h)
    assert r.status_code == 429 and r.headers["Retry-After"] == "900"
    # another account from the same address is not locked by it
    r = web.post("/api/v1/auth/sign-in", json={"email": addr("other"), "password": "wrong-password-1"}, headers=h)
    assert r.status_code == 401


def test_b2_second_factor_rate_limit(web: TestClient, owner: Account) -> None:
    web.cookies.clear()
    h = csrf(web)
    web.post("/api/v1/auth/sign-in", json={"email": owner.email, "password": PASSWORD}, headers=h)
    wrong = "000000" if code_for(owner.secret, 1) != "000000" else "111111"
    statuses = [web.post("/api/v1/auth/mfa", json={"code": wrong}, headers=h).status_code
                for _ in range(get_settings().rate_mfa_per_user)]
    assert set(statuses) == {401}
    r = web.post("/api/v1/auth/mfa", json={"code": code_for(owner.secret, 1)}, headers=h)
    assert r.status_code == 429


def test_b2_anti_forgery(web: TestClient, owner: Account) -> None:
    web.cookies.clear()
    csrf(web)
    r = web.post("/api/v1/auth/sign-in", json={"email": owner.email, "password": PASSWORD})
    assert r.status_code == 403 and r.json()["code"] == "csrf"
    h = csrf(web)
    r = web.post("/api/v1/auth/sign-in", json={"email": owner.email, "password": PASSWORD},
                 headers={**h, "Origin": "https://evil.example"})
    assert r.status_code == 403
    r = web.post("/api/v1/auth/sign-in", json={"email": owner.email, "password": PASSWORD},
                 headers={**h, "Origin": get_settings().public_base_url})
    assert r.status_code == 200


def test_b2_credential_tables_are_reachable_only_through_owned_functions(app_engine: Engine,
                                                                         owner_engine: Engine) -> None:
    from sqlalchemy.exc import ProgrammingError
    for table in ("totp_credential", "recovery_code", "password_reset", "auth_attempt", "session"):
        with pytest.raises(ProgrammingError), app_engine.begin() as c:
            c.execute(text(f"SELECT count(*) FROM {table}"))
    with owner_engine.connect() as c:
        rows = c.execute(text(
            "SELECT p.proname, r.rolname, r.rolsuper, r.rolbypassrls, r.rolcanlogin, p.prosecdef, p.proconfig, "
            "has_function_privilege('claimcheck_worker', p.oid, 'EXECUTE'), "
            "has_function_privilege('claimcheck_app', p.oid, 'EXECUTE') "
            "FROM pg_proc p JOIN pg_roles r ON r.oid = p.proowner WHERE p.proname LIKE 'cc\\_auth\\_%'")).all()
    assert len(rows) == 13
    for name, owner, sup, bypass, login, secdef, config, worker_x, app_x in rows:
        assert (owner, sup, bypass, login, secdef, worker_x, app_x) == (
            "claimcheck_auth_owner", False, False, False, True, False, True), name
        assert "search_path=pg_catalog, public, pg_temp" in config, name
