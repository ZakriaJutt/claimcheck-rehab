"""Regression tests for review round 1 (B1-001..B1-009), reproducing the reviewer's cases A03, A05, A09,
A10, A11, A12, A14 and the publication drift. Synthetic rows only."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from claimcheck_core.evaluation import evaluate_clinic
from claimcheck_core.seed import CatalogueDrift, publish_rules
from tests.fixtures.synthetic import harbourview as hv_rows
from tests.fixtures.synthetic import token
from tests.integration.conftest import ClinicCtx, as_user, drain, upload


def _week(api: TestClient, ctx: ClinicCtx) -> dict:  # type: ignore[type-arg]
    as_user(api, ctx)
    r = api.get("/api/v1/items?view=week")
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def _icbc(n: int, **kw: object) -> dict:  # type: ignore[type-arg]
    row = {"row_no": n, "line_no": 1, "invoice_ref": f"IC-{n:06d}", "date_of_service": "2026-09-20",
           "payer": "ICBC", "billing_code": "ICBC-ST", "amount_invoiced": "97.00", "amount_paid": "0.00",
           "submission_state": "unsubmitted", "state_date": None, "discipline": "physiotherapy",
           "claim_token": None}
    row.update(kw)
    return row


def test_b1_001_rows_rejected_at_finalize_stay_visible_and_counts_add_up(
        api: TestClient, harbourview: ClinicCtx, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reviewer A12: a null date and a null amount used to vanish and the list said nothing needs action."""
    visits = [_icbc(1, date_of_service=None), _icbc(2, amount_invoiced=None)]
    upload(api, harbourview, visits, [])
    drain(monkeypatch)
    body = _week(api, harbourview)
    c = body["counts"]
    assert c["rows_received"] == 2 and c["adds_up"] is True
    assert c["visits"]["unreadable"] == 2 and c["not_checked_total"] == 2
    assert body["summary"] is None
    assert body["banner"] == "2 could not be checked. They are not fine."
    rows = {r["row_no"]: r["reason"] for r in body["groups"]["could_not_check"]}
    assert rows == {1: "row:missing_required", 2: "row:missing_required"}


def test_b1_001_conflicting_duplicates_are_not_checked_exact_repeats_are_counted(
        api: TestClient, harbourview: ClinicCtx, monkeypatch: pytest.MonkeyPatch) -> None:
    same = _icbc(1, submission_state="paid", amount_paid="97.00")
    repeat = {**same, "row_no": 2}
    conflict_a = _icbc(3, invoice_ref="IC-000099", submission_state="paid", amount_paid="97.00")
    conflict_b = {**conflict_a, "row_no": 4, "submission_state": "unsubmitted", "amount_paid": "0.00"}
    upload(api, harbourview, [same, repeat, conflict_a, conflict_b], [])
    drain(monkeypatch)
    c = _week(api, harbourview)["counts"]
    assert c["visits"]["repeated"] == 1 and c["visits"]["unreadable"] == 2
    assert c["adds_up"] is True and c["rows_received"] == 4


def test_b1_001_and_b1_002_summary_only_when_everything_was_checked(
        api: TestClient, harbourview: ClinicCtx, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = hv_rows()
    upload(api, harbourview, rows.visits, rows.claims)
    drain(monkeypatch)
    body = _week(api, harbourview)
    assert body["counts"]["visits"]["checked"] == 1013 and body["counts"]["adds_up"] is True
    assert body["summary"] is not None and "1013 visits checked" in body["summary"]
    rows = hv_rows(seed=3, unknown_states=43)
    upload(api, harbourview, rows.visits, rows.claims, export_date="2026-11-10")
    drain(monkeypatch)
    body = _week(api, harbourview)
    assert body["summary"] is None  # 43 could not be checked: never "nothing needs action"
    assert body["counts"]["visits"]["could_not_check"] == 43


def test_b1_002_rules_not_evaluated_are_listed_and_not_checked(
        api: TestClient, harbourview: ClinicCtx, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reviewer A11/A05: an ICBC visit with no claim link, and Hand Therapy before 2026-09-27."""
    unlinked = _icbc(1, submission_state="paid", amount_paid="97.00")
    hand = _icbc(2, billing_code="ICBC-HT30", amount_invoiced="110.00", amount_paid="110.00",
                 submission_state="paid", date_of_service="2026-09-26")
    upload(api, harbourview, [unlinked, hand], [])
    drain(monkeypatch)
    body = _week(api, harbourview)
    v = body["counts"]["visits"]
    assert v["checked"] == 0 and v["rules_not_evaluated"] == 1 and v["could_not_check"] == 1
    assert body["summary"] is None
    reasons = {r["invoice_ref"]: r["reason"] for r in body["groups"]["could_not_check"]}
    assert reasons["IC-000002"] == "no_rule_version"
    assert "ICBC-03:no_claim_link" in reasons["IC-000001"]


def test_b1_003_rerejection_before_first_export_gives_earliest_limit(
        api: TestClient, harbourview: ClinicCtx, app_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reviewer A09: true first rejection 2026-06-01, re-rejected 2026-09-15, first export shows the
    later date. The limit must be service + 180 = 2026-10-28, never 2026-12-14."""
    tok = token(77, 1)
    v = {"row_no": 1, "line_no": 1, "invoice_ref": "WB-000077", "date_of_service": "2026-05-01", "payer": "WSBC",
         "billing_code": "19102", "amount_invoiced": "95.00", "amount_paid": "0.00", "submission_state": "rejected",
         "state_date": "2026-09-15", "discipline": "physiotherapy", "claim_token": tok}
    c = {"row_no": 1, "claim_token": tok, "payer": "WSBC", "policy_status": "open", "end_date": None,
         "treatments_count": None, "policy_max": None, "next_appointment_date": "2026-12-01",
         "date_of_event": "2026-04-28"}
    upload(api, harbourview, [v], [c], export_date="2026-09-20")
    drain(monkeypatch, on=date(2026, 9, 20))
    evaluate_clinic(app_engine, harbourview.id, date(2026, 11, 1))
    as_user(api, harbourview)
    items = [x for g, xs in _week(api, harbourview)["groups"].items() if g != "could_not_check" for x in xs
             if x["rule_code"] == "WSBC-02"]
    assert len(items) == 1
    assert items[0]["limit_date"] == "2026-10-28" and items[0]["money_class"] == "permanent_certain"


def test_b1_003_observed_unsubmitted_gives_a_bound_that_is_never_later(
        api: TestClient, harbourview: ClinicCtx, app_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    tok = token(78, 1)
    base = {"row_no": 1, "line_no": 1, "invoice_ref": "WB-000078", "date_of_service": "2026-05-01", "payer": "WSBC",
            "billing_code": "19102", "amount_invoiced": "95.00", "amount_paid": "0.00", "discipline": "physiotherapy",
            "claim_token": tok}
    c = {"row_no": 1, "claim_token": tok, "payer": "WSBC", "policy_status": "open", "end_date": None,
         "treatments_count": None, "policy_max": None, "next_appointment_date": "2026-12-01",
         "date_of_event": "2026-04-28"}
    upload(api, harbourview, [{**base, "submission_state": "unsubmitted", "state_date": None}], [c],
           export_date="2026-05-10")
    upload(api, harbourview, [{**base, "submission_state": "rejected", "state_date": "2026-09-01"}], [c],
           export_date="2026-09-07")
    drain(monkeypatch, on=date(2026, 9, 7))
    evaluate_clinic(app_engine, harbourview.id, date(2026, 9, 8))
    items = [x for g, xs in _week(api, harbourview)["groups"].items() if g != "could_not_check" for x in xs
             if x["rule_code"] == "WSBC-02"]
    # never rejected before 2026-05-10 -> limit at least 05-10 + 90 = 08-08; service + 180 = 10-28 is later
    assert items[0]["limit_date"] == "2026-10-28"  # not 2026-11-30 (09-01 + 90)


def test_b1_009_publication_refuses_drift(owner_engine: Engine) -> None:
    with owner_engine.begin() as conn:
        conn.execute(text("UPDATE rule_version SET params = jsonb_set(params, '{limit_days}', '46') "
                          "WHERE rule_code = 'ICBC-01' AND version = 1"))
        with pytest.raises(CatalogueDrift):
            publish_rules(conn, fixtures_passed=True)
        conn.rollback()
    with owner_engine.begin() as conn:
        assert publish_rules(conn, fixtures_passed=True) == 0  # unchanged catalogue: nothing new, no error
