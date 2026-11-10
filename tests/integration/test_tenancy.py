"""IT-06 cross-clinic denial; RLS with no tenant context; every clinic table has a policy (R-05);
append-only grants (T-2.2.5); write-once item fields (MH-08 b)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from claimcheck_core.evaluation import evaluate_clinic
from claimcheck_core.models import CLINIC_OWNED_TABLES, AuditEvent, Item, Visit
from claimcheck_core.tenancy import system_session, tenant_session
from tests.fixtures.synthetic import harbourview as hv_rows
from tests.integration.conftest import TODAY, ClinicCtx, as_user, drain, upload


def _seed_with_item(api: TestClient, ctx: ClinicCtx, monkeypatch: pytest.MonkeyPatch, prefix: str = "HV") -> None:
    rows = hv_rows(prefix=prefix)
    rows.visits[0]["submission_state"] = "unsubmitted"  # ICBC, 2026-08-12: past its limit -> an item
    rows.visits[0]["amount_paid"] = "0.00"
    upload(api, ctx, rows.visits, rows.claims)
    drain(monkeypatch)


def test_it06_other_clinic_gets_404_and_zero_rows(api: TestClient, harbourview: ClinicCtx, seawall: ClinicCtx,
                                                  app_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_with_item(api, harbourview, monkeypatch)
    _seed_with_item(api, seawall, monkeypatch, prefix="SW")
    with tenant_session(app_engine, harbourview.id) as s:
        hv_item = s.scalars(select(Item.id)).first()
        hv_visits = s.scalar(select(func.count()).select_from(Visit))
    assert hv_item is not None and hv_visits == 1184

    as_user(api, seawall)
    r = api.get(f"/api/v1/items/{hv_item}")
    assert r.status_code == 404 and r.json()["code"] == "not_found"
    with tenant_session(app_engine, seawall.id) as s:
        denied = s.scalars(select(AuditEvent).where(AuditEvent.action == "cross_clinic_denied")).all()
        assert len(denied) == 1 and denied[0].object_id == hv_item
        # SQL under the app role with Seawall's setting: zero Harbourview rows
        assert s.scalar(select(func.count()).select_from(Item).where(Item.id == hv_item)) == 0
        assert s.scalar(select(func.count()).select_from(Visit).where(Visit.invoice_ref.like("HV-%"))) == 0
    # a worker job for Harbourview reads only Harbourview
    summary = evaluate_clinic(app_engine, harbourview.id, TODAY)
    assert sum(summary.counts.values()) == 1184
    with tenant_session(app_engine, harbourview.id) as s:
        assert s.scalar(select(func.count()).select_from(Visit).where(Visit.invoice_ref.like("SW-%"))) == 0


def test_no_tenant_context_reads_zero_rows(api: TestClient, harbourview: ClinicCtx, app_engine: Engine,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_with_item(api, harbourview, monkeypatch)
    with system_session(app_engine) as s:
        for table in (*CLINIC_OWNED_TABLES, "clinic"):
            assert s.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0, table  # noqa: S608
    with app_engine.connect() as c:  # a bare connection, no setting at all
        assert c.execute(text("SELECT count(*) FROM visit")).scalar() == 0


def test_app_role_cannot_read_sessions(app_engine: Engine) -> None:
    with pytest.raises(ProgrammingError), app_engine.connect() as c:
        c.execute(text("SELECT count(*) FROM session"))


def test_every_clinic_table_has_rls_policy(owner_engine: Engine) -> None:
    with owner_engine.connect() as c:
        tables = set(c.execute(text(
            "SELECT table_name FROM information_schema.columns WHERE table_schema='public' "
            "AND column_name='clinic_id'")).scalars())
        policied = set(c.execute(text("SELECT tablename FROM pg_policies WHERE schemaname='public'")).scalars())
        forced = dict(c.execute(text(
            "SELECT relname, relforcerowsecurity FROM pg_class WHERE relname = ANY(:t)"), {"t": list(tables)}).all())
    assert tables == set(CLINIC_OWNED_TABLES)
    assert tables <= policied
    assert all(forced.values())


@pytest.mark.parametrize("table", ["audit_event", "item_event", "visit_snapshot"])
def test_append_only_tables(app_engine: Engine, harbourview: ClinicCtx, table: str) -> None:
    for stmt in (f"UPDATE {table} SET created_at = now()", f"DELETE FROM {table}"):
        with pytest.raises(DBAPIError), tenant_session(app_engine, harbourview.id) as s:
            s.execute(text(stmt))


def test_write_once_item_fields(api: TestClient, harbourview: ClinicCtx, app_engine: Engine,
                                monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_with_item(api, harbourview, monkeypatch)
    with pytest.raises(DBAPIError), tenant_session(app_engine, harbourview.id) as s:
        s.execute(text("UPDATE item SET first_flagged_on = first_flagged_on - 1"))
    with pytest.raises(DBAPIError), tenant_session(app_engine, harbourview.id) as s:
        s.execute(text("UPDATE item SET reached_near_limit_on = reached_near_limit_on + 1 "
                       "WHERE reached_near_limit_on IS NOT NULL"))
        raise AssertionError("trigger did not fire")  # pragma: no cover


def test_cannot_insert_row_for_another_clinic(app_engine: Engine, harbourview: ClinicCtx, seawall: ClinicCtx) -> None:
    with pytest.raises(DBAPIError), tenant_session(app_engine, seawall.id) as s:
        s.execute(text("INSERT INTO audit_event (clinic_id, action, outcome, correlation_id) "
                       "VALUES (:c, 'x', 'x', gen_random_uuid())"), {"c": harbourview.id})
