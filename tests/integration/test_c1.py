"""C1 (2026-11-11) through the database and the API, synthetic rows only.

- A visit past ICBC's 45 days is listed as "past payer deadline - payment at payer's discretion"; it
  becomes "confirmed unpaid" only after staff record the payer's outcome (`payer_declined`).
- Publication marks a replaced rule version `superseded` before its successor goes in.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text

from claimcheck_core.evaluation import evaluate_clinic
from claimcheck_core.models import Item
from claimcheck_core.seed import publish_rules
from claimcheck_core.tenancy import tenant_session
from tests.integration.conftest import TODAY, ClinicCtx, as_user, drain, upload


def _week(api: TestClient, ctx: ClinicCtx) -> dict[str, Any]:
    as_user(api, ctx)
    r = api.get("/api/v1/items?view=week")
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def _groups_of(body: dict[str, Any], rule: str) -> dict[str, dict[str, Any]]:
    return {g: x for g, xs in body["groups"].items() if g != "could_not_check" for x in xs if x["rule_code"] == rule}


def test_c1_past_deadline_is_discretion_until_payer_outcome_recorded(
        api: TestClient, harbourview: ClinicCtx, app_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    v = {"row_no": 1, "line_no": 1, "invoice_ref": "C1-IC-0001", "date_of_service": "2026-09-20",
         "payer": "ICBC", "billing_code": "ICBC-ST", "amount_invoiced": "97.00", "amount_paid": "0.00",
         "submission_state": "unsubmitted", "state_date": None, "discipline": "physiotherapy", "claim_token": None}
    upload(api, harbourview, [v], [], export_date="2026-11-09")
    drain(monkeypatch, on=TODAY)  # limit 2026-11-04 has passed
    found = _groups_of(_week(api, harbourview), "ICBC-01")
    assert list(found) == ["past_deadline_payer_discretion"]
    item = found["past_deadline_payer_discretion"]
    assert (item["money_class"], item["reason"]) == ("past_deadline_discretionary", "past_limit_payer_discretion")

    headers = as_user(api, harbourview)
    r = api.post(f"/api/v1/items/{item['id']}/events",
                 json={"kind": "outcome", "outcome": "payer_declined", "idempotency_key": uuid.uuid4().hex},
                 headers={**headers, "If-Match": str(item["version"])})
    assert r.status_code == 200 and r.json()["status"] == "open", r.text
    evaluate_clinic(app_engine, harbourview.id, date(2026, 11, 11))
    found = _groups_of(_week(api, harbourview), "ICBC-01")
    assert list(found) == ["confirmed_unpaid"] and found["confirmed_unpaid"]["money_class"] == "confirmed_unpaid"
    with tenant_session(app_engine, harbourview.id) as s:
        it = s.scalars(select(Item).where(Item.rule_code == "ICBC-01")).one()
        assert it.class_at_first_flag == "past_deadline_discretionary"  # written once, the date-only class


def test_c1_database_refuses_the_old_class_name(owner_engine: Engine) -> None:
    with owner_engine.connect() as c:
        defs = c.execute(text("SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                              "WHERE conname = 'item_money_class_check'")).scalar_one()
    assert "past_deadline_discretionary" in defs and "confirmed_unpaid" in defs
    assert "permanent_discretionary" not in defs


def test_c1_publication_supersedes_replaced_version(owner_engine: Engine) -> None:
    with owner_engine.begin() as conn:
        # A pre-C1 database: WSBC-10 version 1 still published (on a range that does not overlap v2).
        conn.execute(text(
            "INSERT INTO rule_version (rule_code, version, effective_from, effective_to, params, source_citation, "
            "source_id, status, fixtures_passed_at, published_at) VALUES ('WSBC-10', 1, '2020-01-01', '2020-12-31', "
            "'{\"unpaid_days\": 30}', 'Gap G-4', 'SRC-19', 'published', now(), now())"))
        publish_rules(conn, fixtures_passed=True)
        rows = dict(conn.execute(text(
            "SELECT version, status FROM rule_version WHERE rule_code = 'WSBC-10'")).all())
        assert rows == {1: "superseded", 2: "published"}
        conn.rollback()
