"""E2E-09 (API-level counterpart; no UI in B1), IT-07, IT-08, IT-16, IT-17, UT-17 through the database."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text

from claimcheck_core.dates import local_today
from claimcheck_core.evaluation import evaluate_clinic, staleness_check
from claimcheck_core.models import AuditEvent, Item, ItemEvent
from claimcheck_core.tenancy import tenant_session
from tests.fixtures.synthetic import harbourview as hv_rows
from tests.fixtures.synthetic import token
from tests.integration.conftest import TODAY, ClinicCtx, as_user, drain, upload


def _items(api: TestClient, ctx: ClinicCtx) -> dict[str, Any]:
    as_user(api, ctx)
    r = api.get("/api/v1/items?view=week")
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def test_e2e09_api_unknown_states_listed_and_never_fine(api: TestClient, harbourview: ClinicCtx,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    rows = hv_rows(unknown_states=43)
    upload(api, harbourview, rows.visits, rows.claims)
    drain(monkeypatch)
    body = _items(api, harbourview)
    v = body["counts"]["visits"]
    assert (v["checked"], v["could_not_check"], v["no_rules_applied"]) == (970, 43, 171)
    assert body["counts"]["adds_up"] is True and body["counts"]["rows_received"] == 1184 + 388
    assert len(body["groups"]["could_not_check"]) == 43
    assert {x["reason"] for x in body["groups"]["could_not_check"]} == {"unknown_state"}
    assert body["banner"] == "43 could not be checked. They are not fine."
    # Fix round 1 ruling (B1-001): "nothing needs action" only when every row was checked.
    assert body["summary"] is None


def test_nothing_needs_action_not_said_before_evaluation(api: TestClient, harbourview: ClinicCtx) -> None:
    rows = hv_rows()
    upload(api, harbourview, rows.visits, rows.claims)  # finalize queued, nothing evaluated yet
    body = _items(api, harbourview)
    assert body["summary"] is None


def _wsbc_export(ctx_api: TestClient, ctx: ClinicCtx, state: str, export_date: str) -> None:
    tok = token(99, 1)
    visit = {"row_no": 1, "line_no": 1, "invoice_ref": "WB-000001", "date_of_service": "2026-10-01",
             "payer": "WSBC", "billing_code": "19102", "amount_invoiced": "95.00", "amount_paid": "0.00",
             "submission_state": state, "state_date": None, "discipline": "physiotherapy", "claim_token": tok}
    claim = {"row_no": 1, "claim_token": tok, "payer": "WSBC", "policy_status": "open", "end_date": None,
             "treatments_count": None, "policy_max": None, "next_appointment_date": "2026-12-01",
             "date_of_event": "2026-09-25"}
    _, r = upload(ctx_api, ctx, [visit], [claim], export_date=export_date)
    assert r.status_code == 202, r.text


def _item(api: TestClient, ctx: ClinicCtx, rule: str) -> dict[str, Any]:
    body = _items(api, ctx)
    rows = [x for g, xs in body["groups"].items() if g != "could_not_check" for x in xs if x["rule_code"] == rule]
    assert len(rows) == 1, rows
    return rows[0]


def _event(api: TestClient, ctx: ClinicCtx, item: dict[str, Any], outcome: str, version: int | None = None,
           key: str | None = None) -> Any:
    headers = as_user(api, ctx)
    return api.post(f"/api/v1/items/{item['id']}/events",
                    json={"kind": "outcome", "outcome": outcome, "idempotency_key": key or uuid.uuid4().hex},
                    headers={**headers, "If-Match": str(version if version is not None else item["version"])})


def test_it07_two_saves_on_same_version(api: TestClient, harbourview: ClinicCtx,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    _wsbc_export(api, harbourview, "unsubmitted", "2026-11-09")
    drain(monkeypatch)
    item = _item(api, harbourview, "WSBC-01")
    a = _event(api, harbourview, item, "submitted")
    b = _event(api, harbourview, item, "written_off")
    assert sorted([a.status_code, b.status_code]) == [200, 409]
    assert b.json()["code"] == "stale_version"
    replay = _event(api, harbourview, item, "submitted", version=item["version"] + 1, key="replay-key-1")
    again = _event(api, harbourview, item, "submitted", version=item["version"] + 2, key="replay-key-1")
    assert replay.status_code == 200 and again.json()["replayed"] is True


def test_it08_marked_submitted_export_disagrees_item_reopens_then_confirms(
        api: TestClient, harbourview: ClinicCtx, app_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    _wsbc_export(api, harbourview, "unsubmitted", "2026-11-09")
    drain(monkeypatch, on=date(2026, 11, 10))
    item = _item(api, harbourview, "WSBC-01")
    assert _event(api, harbourview, item, "submitted").json()["status"] == "awaiting_confirmation"
    assert _item(api, harbourview, "WSBC-01")["status"] == "awaiting_confirmation"  # still visible

    # Later exports must post-date the outcome, which is stamped with the real clock.
    base = max(local_today(), TODAY)
    week2, week3 = base + timedelta(days=6), base + timedelta(days=13)
    _wsbc_export(api, harbourview, "unsubmitted", week2.isoformat())  # Jane still says unsubmitted
    drain(monkeypatch, on=week2)
    assert _item(api, harbourview, "WSBC-01")["status"] == "open"

    _wsbc_export(api, harbourview, "submitted", week3.isoformat())
    drain(monkeypatch, on=week3)
    with tenant_session(app_engine, harbourview.id) as s:
        it = s.scalars(select(Item).where(Item.rule_code == "WSBC-01")).one()
        kinds = [e.kind for e in s.scalars(select(ItemEvent).where(ItemEvent.item_id == it.id)
                                          .order_by(ItemEvent.created_at))]
    assert it.status == "confirmed"
    assert kinds == ["flagged", "outcome", "reopened", "confirmed"]


def test_ut17_db_path_portal_not_received_makes_icbc_01_near_limit(
        api: TestClient, harbourview: ClinicCtx, app_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    tok = token(98, 1)
    visit = {"row_no": 1, "line_no": 1, "invoice_ref": "IC-000001", "date_of_service": "2026-10-01",
             "payer": "ICBC", "billing_code": "ICBC-ST", "amount_invoiced": "97.00", "amount_paid": "0.00",
             "submission_state": "submitted", "state_date": None, "discipline": "physiotherapy", "claim_token": tok}
    claim = {"row_no": 1, "claim_token": tok, "payer": "ICBC", "policy_status": "open", "end_date": "2027-01-31",
             "treatments_count": 1, "policy_max": 25, "next_appointment_date": None, "date_of_event": "2026-09-28"}
    upload(api, harbourview, [visit], [claim], export_date="2026-10-15")
    drain(monkeypatch, on=date(2026, 10, 15))
    item = _item(api, harbourview, "ICBC-07")
    assert (item["reason"], item["limit_date"], item["submit_by"]) == ("verify_in_portal", "2026-11-15", "2026-11-14")
    r = _event(api, harbourview, item, "portal_not_received")
    assert r.status_code == 200
    evaluate_clinic(app_engine, harbourview.id, date(2026, 11, 10))
    icbc01 = _item(api, harbourview, "ICBC-01")
    assert icbc01["near_limit_since"] == "2026-11-10" and icbc01["days_left"] == 5


def test_it16_old_import_and_stopped_evaluation(api: TestClient, harbourview: ClinicCtx, owner_engine: Engine,
                                                app_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = hv_rows()
    upload(api, harbourview, rows.visits, rows.claims, export_date="2026-11-01")  # 9 days before TODAY
    drain(monkeypatch)
    with owner_engine.begin() as c:
        c.execute(text("UPDATE evaluation_run SET finished_at = now() - interval '37 hours'"))
    fr = _items(api, harbourview)["freshness"]
    assert fr["last_export_date"] == "2026-11-01" and fr["import_stale"] is True
    assert fr["evaluation_stale"] is True and fr["last_evaluated_at"] is not None
    staleness_check(app_engine, harbourview.id, datetime.now(tz=UTC))
    with tenant_session(app_engine, harbourview.id) as s:
        kinds = set(s.scalars(select(AuditEvent.outcome).where(AuditEvent.action == "operator_alert")))
    assert {"import_stale", "evaluation_stale"} <= kinds


def test_it17_planted_escape_m09_equals_one(api: TestClient, harbourview: ClinicCtx, owner_engine: Engine,
                                            app_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = hv_rows()
    bid, _ = upload(api, harbourview, rows.visits, rows.claims)
    drain(monkeypatch)
    with owner_engine.begin() as c:  # present in imports since 2026-09-20, limit 2026-10-16, no item
        c.execute(text(
            "INSERT INTO visit (clinic_id, invoice_ref, payer, discipline, date_of_service, billing_code, "
            "amount_invoiced, submission_state, first_seen_batch_id, first_seen_export_date, last_batch_id, "
            "last_export_date, check_status) VALUES (:c, 'HV-ESCAPE', 'ICBC', 'physiotherapy', '2026-09-01', "
            "'ICBC-ST', 97.00, 'unsubmitted', :b, '2026-09-20', :b, '2026-11-09', 'in_scope')"),
            {"c": harbourview.id, "b": bid})
    summary = evaluate_clinic(app_engine, harbourview.id, TODAY)
    assert len(summary.escapes) == 1
    as_user(api, harbourview, role="owner")
    report = api.get("/api/v1/pilot-report").json()
    assert report["m09_escapes"] == 1 and report["escapes"][0]["invoice_ref"] == "HV-ESCAPE"
    with tenant_session(app_engine, harbourview.id) as s:
        assert "m09_escape" in set(s.scalars(select(AuditEvent.outcome).where(AuditEvent.action == "operator_alert")))
    as_user(api, harbourview, role="staff")
    assert api.get("/api/v1/pilot-report").status_code == 403  # owner only


def test_could_not_check_share_alert(api: TestClient, harbourview: ClinicCtx, app_engine: Engine,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
    rows = hv_rows(unknown_states=212)  # TRD HCF-1 scenario: Jane renamed a state
    upload(api, harbourview, rows.visits, rows.claims)
    drain(monkeypatch)
    with tenant_session(app_engine, harbourview.id) as s:
        assert "could_not_check_share" in set(s.scalars(select(AuditEvent.outcome)))
    assert _items(api, harbourview)["banner"] == "212 could not be checked. They are not fine."
