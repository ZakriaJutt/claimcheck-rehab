"""Round-3 hardening (B1-008 residual): `cc_session_principal` has a dedicated non-superuser owner."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import ProgrammingError

from claimcheck_api.deps import hash_token
from tests.integration.conftest import ClinicCtx

FN = "cc_session_principal(text, integer)"


def test_session_lookup_owner_is_dedicated_non_superuser(owner_engine: Engine) -> None:
    with owner_engine.connect() as c:
        owner, sup, bypass, login, inherit, secdef, config = c.execute(text(
            "SELECT r.rolname, r.rolsuper, r.rolbypassrls, r.rolcanlogin, r.rolinherit, p.prosecdef, p.proconfig "
            "FROM pg_proc p JOIN pg_roles r ON r.oid = p.proowner WHERE p.proname = 'cc_session_principal'")).one()
        assert (owner, sup, bypass, login, inherit, secdef) == (
            "claimcheck_session_owner", False, False, False, False, True)
        sp = next(x for x in config if x.startswith("search_path="))
        assert sp.split("=", 1)[1].replace(" ", "").split(",") == ["pg_catalog", "public", "pg_temp"]
        # EXECUTE: owner and claimcheck_app only; not PUBLIC, not the worker.
        holders = set(c.execute(text(
            "SELECT CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE g.rolname END "
            "FROM pg_proc p, aclexplode(p.proacl) a LEFT JOIN pg_roles g ON g.oid = a.grantee "
            "WHERE p.proname = 'cc_session_principal' AND a.privilege_type = 'EXECUTE'")).scalars())
        assert holders == {"claimcheck_session_owner", "claimcheck_app"}
        # The owner holds exactly SELECT/UPDATE on session and SELECT on app_user, nothing else.
        grants = set(c.execute(text(
            "SELECT table_name || ':' || privilege_type FROM information_schema.role_table_grants "
            "WHERE grantee = 'claimcheck_session_owner'")).scalars())
        assert grants == {"session:SELECT", "session:UPDATE", "app_user:SELECT"}
        assert c.execute(text("SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid "
                              "OR r.oid = m.member WHERE r.rolname = 'claimcheck_session_owner'")).scalar() == 0


def test_session_lookup_still_works_for_app_and_refuses_worker(
        app_engine: Engine, worker_engine: Engine, harbourview: ClinicCtx) -> None:
    with app_engine.begin() as c:
        rows = c.execute(text(f"SELECT * FROM {FN.split('(')[0]}(:h, 30)"),
                         {"h": hash_token(harbourview.staff_token)}).mappings().all()
    assert [(r["clinic_id"], r["role"]) for r in rows] == [(harbourview.id, "staff")]
    with pytest.raises(ProgrammingError), worker_engine.begin() as c:
        c.execute(text("SELECT * FROM cc_session_principal(:h, 30)"), {"h": hash_token(harbourview.staff_token)})
    for sql in ("SET ROLE claimcheck_session_owner", "SELECT * FROM session",
                f"ALTER FUNCTION {FN} SET search_path = pg_temp, public"):
        with pytest.raises(ProgrammingError), app_engine.begin() as c:
            c.execute(text(sql))


def test_temp_table_shadowing_does_not_reach_the_lookup(app_engine: Engine, harbourview: ClinicCtx) -> None:
    """pg_temp is last on the pinned search_path, so a planted temp `session` is never read."""
    with app_engine.begin() as c:
        c.execute(text("CREATE TEMP TABLE session (user_id uuid, token_hash text, mfa_passed boolean, "
                       "last_seen_at timestamptz, expires_at timestamptz, revoked_at timestamptz) ON COMMIT DROP"))
        c.execute(text("INSERT INTO pg_temp.session VALUES (:u, 'planted', true, now(), now() + interval '1 hour', "
                       "NULL)"), {"u": harbourview.owner_id})
        assert c.execute(text("SELECT count(*) FROM cc_session_principal('planted', 30)")).scalar() == 0
