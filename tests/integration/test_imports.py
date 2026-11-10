"""IT-01, IT-02, IT-03, IT-04, IT-05, IT-09, IT-18 and the API side of UT-12 and UT-15."""

from __future__ import annotations

import time
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text

from claimcheck_core.identifier_scan import identifier_scan
from claimcheck_core.models import AuditEvent, ImportBatch, ImportRow, Visit, VisitSnapshot
from claimcheck_core.tenancy import tenant_session
from tests.fixtures.synthetic import harbourview as hv_rows
from tests.integration.conftest import TODAY, ClinicCtx, as_user, drain, upload


def _count(engine: Engine, ctx: ClinicCtx, model: type) -> int:
    with tenant_session(engine, ctx.id) as s:
        return int(s.scalar(select(func.count()).select_from(model)) or 0)


def _batch(engine: Engine, ctx: ClinicCtx, bid: str) -> ImportBatch:
    with tenant_session(engine, ctx.id) as s:
        b = s.get(ImportBatch, bid)
        assert b is not None
        return b


def test_it01_base_fixture_import_counts_add_up(api: TestClient, harbourview: ClinicCtx, app_engine: Engine,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    rows = hv_rows()
    assert rows.counts() == {"ICBC": 702, "WSBC": 311, "OTHER": 171}
    bid, r = upload(api, harbourview, rows.visits, rows.claims)
    assert r.status_code == 202
    drain(monkeypatch)
    b = _batch(app_engine, harbourview, bid)
    assert b.status == "completed"
    assert (b.rows_received, b.rows_accepted, b.rows_rejected, b.rows_duplicate) == (1572, 1572, 0, 0)
    assert _count(app_engine, harbourview, Visit) == 1184
    got = api.get(f"/api/v1/imports/{bid}").json()
    assert got["rows_accepted"] == got["rows_received"]


def test_it02_same_content_returns_same_batch(api: TestClient, harbourview: ClinicCtx, app_engine: Engine,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    rows = hv_rows()
    bid, _ = upload(api, harbourview, rows.visits, rows.claims)
    drain(monkeypatch)
    bid2, r = upload(api, harbourview, rows.visits, rows.claims)
    assert bid2 == bid and r.status_code == 200 and r.json()["created"] is False
    assert _count(app_engine, harbourview, ImportBatch) == 1
    assert _count(app_engine, harbourview, Visit) == 1184


def test_it03_unreadable_rows_are_listed(api: TestClient, harbourview: ClinicCtx, app_engine: Engine,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    rows = hv_rows()
    for i in (5, 77, 400):  # the browser could not read a required cell
        rows.visits[i]["date_of_service"] = None
    bid, r = upload(api, harbourview, rows.visits, rows.claims)
    drain(monkeypatch)
    got = api.get(f"/api/v1/imports/{bid}").json()
    assert got["status"] == "completed_with_rejects"
    assert got["rows_rejected"] == 3
    assert [x["row_no"] for x in got["rejected_rows"]] == [6, 78, 401]
    assert {x["reason"] for x in got["rejected_rows"]} == {"missing_required"}
    assert got["rows_received"] == got["rows_accepted"] + got["rows_rejected"] + got["rows_duplicate"]


def test_it04_5000_rows_finalize_within_60_seconds(api: TestClient, harbourview: ClinicCtx, app_engine: Engine,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    visits = []
    claims = []
    for k in range(5):
        r = hv_rows(seed=10 + k, prefix=f"H{k}")
        visits += r.visits[:1000]
        claims += r.claims
    for i, v in enumerate(visits, 1):
        v["row_no"] = i
    for i, c in enumerate(claims, 1):
        c["row_no"] = i
    bid, r = upload(api, harbourview, visits, claims)
    assert r.status_code == 202
    started = time.monotonic()
    drain(monkeypatch, max_jobs=1)  # the finalize job only
    elapsed = time.monotonic() - started
    assert _batch(app_engine, harbourview, bid).status == "completed"
    assert elapsed < 60, elapsed


def test_it05_older_export_does_not_overwrite_current_state(api: TestClient, harbourview: ClinicCtx,
                                                            app_engine: Engine,
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    newer = hv_rows()
    older = hv_rows()
    target = newer.visits[0]["invoice_ref"]
    older.visits[0]["submission_state"] = "unsubmitted"
    older.visits[0]["amount_paid"] = "0.00"
    upload(api, harbourview, newer.visits, newer.claims, export_date="2026-11-09")
    drain(monkeypatch)
    upload(api, harbourview, older.visits, older.claims, export_date="2026-11-02")
    drain(monkeypatch)
    with tenant_session(app_engine, harbourview.id) as s:
        v = s.scalar(select(Visit).where(Visit.invoice_ref == target))
        assert v is not None
        assert v.submission_state == "paid" and v.last_export_date == date(2026, 11, 9)
        snaps = s.scalars(select(VisitSnapshot).where(VisitSnapshot.visit_id == v.id)
                          .order_by(VisitSnapshot.export_date)).all()
        assert [(x.export_date, x.submission_state) for x in snaps] == [
            (date(2026, 11, 2), "unsubmitted"), (date(2026, 11, 9), "paid")]
        assert v.first_seen_export_date == date(2026, 11, 2)


def _assert_rejected_whole(api: TestClient, ctx: ClinicCtx, engine: Engine, bid: str, r: object) -> None:
    assert r.status_code == 422, r.text  # type: ignore[attr-defined]
    body = r.json()  # type: ignore[attr-defined]
    assert body["code"] == "identifier_guard"
    assert _count(engine, ctx, ImportRow) == 0
    assert _batch(engine, ctx, bid).status == "rejected_guard"
    with tenant_session(engine, ctx.id) as s:
        ev = s.scalars(select(AuditEvent).where(AuditEvent.action == "import_rejected_guard",
                                                 AuditEvent.object_id == bid)).all()
        assert len(ev) == 1
        flat = str(ev[0].meta)
        for v in ("Priya", "Sharma", "1984", "9876543210", "HV-"):
            assert v not in flat  # counts and codes only, no values


def test_ut12_unknown_key_and_name_shaped_ref_rejected_whole(api: TestClient, harbourview: ClinicCtx,
                                                             app_engine: Engine) -> None:
    rows = hv_rows()
    rows.visits[3]["patient_name"] = "Priya Sharma"
    bid, r = upload(api, harbourview, rows.visits, rows.claims)
    _assert_rejected_whole(api, harbourview, app_engine, bid, r)
    assert "Priya" not in r.text and "patient_name" not in r.text  # no value or key echoed

    rows = hv_rows(seed=2)
    rows.visits[3]["invoice_ref"] = "Priya Sharma"
    bid, r = upload(api, harbourview, rows.visits, rows.claims)
    _assert_rejected_whole(api, harbourview, app_engine, bid, r)
    assert "Priya" not in r.text


@pytest.mark.parametrize("variant", ["phn_like", "surnames", "repeating_patient_numbers", "birth_date"])
def test_ut15_guard_fixtures_rejected_whole(api: TestClient, harbourview: ClinicCtx, app_engine: Engine,
                                            variant: str) -> None:
    rows = hv_rows()
    vis = rows.visits[:200]
    for i, v in enumerate(vis):
        if variant == "phn_like":
            v["invoice_ref"] = f"9{(123456789 + i * 7919) % 10**9:09d}"  # ten digits, PHN-shaped
        elif variant == "surnames":
            v["invoice_ref"] = ["Nguyen", "Okafor", "Lindqvist", "Tanaka"][i % 4] + ("" if i % 2 else "a")
        elif variant == "repeating_patient_numbers":
            v["invoice_ref"] = f"P{i % 60:04d}"  # 30% distinct
    if variant == "birth_date":
        rows.claims[0]["date_of_event"] = "1984-06-02"
    bid, r = upload(api, harbourview, vis, rows.claims)
    _assert_rejected_whole(api, harbourview, app_engine, bid, r)


def test_ut15_known_residual_gap_80_percent_distinct_passes(api: TestClient, harbourview: ClinicCtx,
                                                            app_engine: Engine,
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """Recorded residual gap (F-005): patient numbers with 80% distinct values are NOT caught."""
    rows = hv_rows()
    vis = rows.visits[:200]
    for i, v in enumerate(vis):
        v["invoice_ref"] = f"P{i % 160:04d}"
        v["line_no"] = 1 + i // 160
    bid, r = upload(api, harbourview, vis, [])
    assert r.status_code == 202
    drain(monkeypatch)
    assert _batch(app_engine, harbourview, bid).status == "completed"


def test_it09_guard_failure_stores_nothing_and_audits_without_values(api: TestClient, harbourview: ClinicCtx,
                                                                     app_engine: Engine) -> None:
    rows = hv_rows()
    headers = as_user(api, harbourview)
    r = api.post("/api/v1/imports", json={"export_date": "2026-11-09", "profile_sales_version": 1,
                                          "profile_policies_version": 1},
                 headers={**headers, "Idempotency-Key": "a" * 64})
    bid = r.json()["id"]
    ok = api.post(f"/api/v1/imports/{bid}/rows", json={"visits": rows.visits[:100]}, headers=headers)
    assert ok.status_code == 200
    bad = rows.visits[100:200]
    for v in bad:
        v["invoice_ref"] = "9876543210"
    r = api.post(f"/api/v1/imports/{bid}/rows", json={"visits": bad}, headers=headers)
    _assert_rejected_whole(api, harbourview, app_engine, bid, r)  # earlier staged rows removed too
    assert "9876543210" not in r.text
    r = api.post(f"/api/v1/imports/{bid}/rows", json={"visits": rows.visits[:10]}, headers=headers)
    assert r.status_code == 409  # the batch is closed
    with tenant_session(app_engine, harbourview.id) as s:
        alerts = s.scalars(select(AuditEvent.outcome).where(AuditEvent.action == "operator_alert")).all()
    assert "guard_rejection" in alerts


def test_it18_identifier_scan_on_stored_rows_alerts_and_pauses(api: TestClient, harbourview: ClinicCtx,
                                                                app_engine: Engine, owner_engine: Engine,
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    rows = hv_rows()
    upload(api, harbourview, rows.visits, rows.claims)
    drain(monkeypatch)
    with owner_engine.begin() as c:  # bypass the API, as a guard gap would
        c.execute(text("UPDATE visit SET invoice_ref = '9123456789' WHERE invoice_ref = 'HV-000001'"))
    failures = identifier_scan(app_engine, harbourview.id, TODAY)
    assert [f.check for f in failures] == ["phn_like"]
    with tenant_session(app_engine, harbourview.id) as s:
        assert "identifier_scan_match" in s.scalars(select(AuditEvent.outcome)).all()
    r = api.post("/api/v1/imports", json={"export_date": "2026-11-10", "profile_sales_version": 1,
                                          "profile_policies_version": 1},
                 headers={**as_user(api, harbourview), "Idempotency-Key": "b" * 64})
    assert r.status_code == 409 and r.json()["code"] == "imports_paused"
