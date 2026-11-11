"""Regression tests for review round 1, engine and guard level (reviewer cases A03, A05, A09, A10, A11)."""

from __future__ import annotations

import pytest

from claimcheck_core.intake.guard import check_rows
from claimcheck_core.rules.payer_rules import wsbc_correction_limit
from tests.fixtures.factories import D, claim, outcomes, result, run, visit


@pytest.mark.parametrize("payer,code,amount,unpaid_rule", [
    ("ICBC", "ICBC-ST", "97.00", "ICBC-07"), ("WSBC", "19102", "95.00", "WSBC-10")])
def test_b1_004_partly_paid_never_reads_clear(payer: str, code: str, amount: str, unpaid_rule: str) -> None:
    c = claim(payer=payer, treatments_count=3, policy_max=25, end_date=D("2026-12-31"),
              date_of_event=D("2026-09-01"), policy_status="open", next_appointment_date=D("2026-11-20"))
    v = visit(payer=payer, billing_code=code, amount_invoiced=amount, amount_paid="10.00",
              submission_state="partly_paid", date_of_service="2026-09-20", claim_id=c.id)
    ev = run([v], [c], on="2026-11-10")
    r = result(ev, v.id, unpaid_rule)
    assert (r.outcome, r.reason, r.money_class) == ("flag", "partly_paid_balance", "delayed_cash")
    assert r.amount is not None and r.amount == r.amount.__class__(amount) - r.amount.__class__("10.00")
    assert set(outcomes(ev, v.id).values()) != {"clear"}


def test_b1_004_icbc_rejected_is_not_evaluated_never_clear() -> None:
    c = claim(treatments_count=3, policy_max=25, end_date=D("2026-12-31"), date_of_event=D("2026-09-01"))
    v = visit(submission_state="rejected", amount_paid="10.00", date_of_service="2026-09-20", claim_id=c.id)
    ev = run([v], [c], on="2026-11-10")
    for rule in ("ICBC-01", "ICBC-07"):
        r = result(ev, v.id, rule)
        assert (r.outcome, r.reason) == ("not_evaluated", "icbc_rejected_no_rule")
    assert ev.scopes[v.id].status == "rules_not_evaluated"


def test_b1_002_hand_therapy_before_its_date_is_could_not_check_at_scope() -> None:
    v = visit(billing_code="ICBC-HT30", amount_invoiced="110.00", date_of_service="2026-09-26",
              submission_state="paid", amount_paid="110.00")
    ev = run([v], on="2026-10-01")
    assert ev.scopes[v.id].status == "could_not_check"
    assert ev.scopes[v.id].reasons == ("no_rule_version",)
    assert "clear" not in outcomes(ev, v.id).values()


def test_b1_002_unlinked_icbc_visit_is_rules_not_evaluated() -> None:
    v = visit(submission_state="paid", amount_paid="97.00", date_of_service="2026-09-20")
    ev = run([v], on="2026-11-10")
    s = ev.scopes[v.id]
    assert s.status == "rules_not_evaluated"
    assert {"ICBC-02:no_claim_link", "ICBC-03:no_claim_link", "ICBC-08:no_claim_link"} <= set(s.reasons)


def test_b1_002_claim_level_not_evaluated_reaches_its_visits() -> None:
    c = claim(treatments_count=None, policy_max=25, end_date=D("2026-12-31"))  # ICBC-02 cannot run
    v = visit(submission_state="paid", amount_paid="97.00", date_of_service="2026-09-20", claim_id=c.id)
    ev = run([v], [c], on="2026-11-10")
    assert ev.scopes[v.id].reasons == ("ICBC-02:missing_treatment_count",)


def test_b1_003_rerejection_case_act_by_is_service_plus_180() -> None:
    """Reviewer A09: true first rejection 06-01, re-rejected 09-15, nothing observed before. Act by
    2026-10-28; since round 2 (B1-010) the loss is certain only after 09-15 + 90 = 2026-12-14."""
    v = visit(payer="WSBC", billing_code="19102", amount_invoiced="95.00", date_of_service="2026-05-01",
              submission_state="rejected", state_date=D("2026-09-15"), rejected_not_before=None,
              rejected_by=D("2026-09-15"))
    r = result(run([v], on="2026-11-01"), v.id, "WSBC-02")
    assert (r.limit_date, r.latest_limit, r.money_class) == (D("2026-10-28"), D("2026-12-14"), "delayed_cash")
    assert wsbc_correction_limit(D("2026-05-01"), None) == D("2026-10-28")


@pytest.mark.parametrize("on,money_class,reason,near", [
    ("2026-10-14", "delayed_cash", "rejected_earliest_limit", True),     # 14 days before the earliest
    ("2026-10-28", "delayed_cash", "rejected_earliest_limit", True),     # earliest possible limit itself
    ("2026-10-29", "delayed_cash", "check_first_rejection_date", True),  # past earliest: at risk
    ("2026-12-09", "delayed_cash", "check_first_rejection_date", True),  # latest possible limit itself
    ("2026-12-10", "permanent_certain", "past_correction_limit", True),  # past latest: certain loss
])
def test_b1_010_backlog_rejection_two_bounds(on: str, money_class: str, reason: str, near: bool) -> None:
    """Reviewer A19: first seen already rejected (onboarding backlog), service 2026-05-01, state date
    2026-09-10. Act by 2026-10-28; certain loss only after 2026-12-09."""
    v = visit(payer="WSBC", billing_code="19102", amount_invoiced="95.00", date_of_service="2026-05-01",
              submission_state="rejected", state_date=D("2026-09-10"), rejected_by=D("2026-09-10"))
    r = result(run([v], on=on), v.id, "WSBC-02")
    assert (r.limit_date, r.latest_limit) == (D("2026-10-28"), D("2026-12-09"))
    assert (r.money_class, r.reason, r.near_limit) == (money_class, reason, near)


def test_b1_010_items_between_bounds_are_not_lost_and_not_in_permanent_figures() -> None:
    from claimcheck_core.items import next_item
    from claimcheck_core.measure import audit_figures
    v = visit(payer="WSBC", billing_code="19102", amount_invoiced="95.00", date_of_service="2026-05-01",
              submission_state="rejected", state_date=D("2026-09-10"), rejected_by=D("2026-09-10"))
    ev = run([v], on="2026-11-01")
    fig = audit_figures(ev, [v], D("2026-11-01"))
    assert fig.wsbc_past_limit_balance == 0 and fig.wsbc_at_risk_balance == 95
    item, _ = next_item(None, result(ev, v.id, "WSBC-02"), D("2026-11-01"), v)
    assert item is not None and item.money_class == "delayed_cash" and item.reached_near_limit_on is not None
    later = result(run([v], on="2026-12-10"), v.id, "WSBC-02")
    item2, events = next_item(item, later, D("2026-12-10"), v)
    assert item2 is not None and item2.money_class == "permanent_certain" and "class_changed" in events


@pytest.mark.parametrize("ref", ["9123456782", "9123-456-782", "9-123-456-782", "P9123456782", "9123456782-1"])
def test_b1_006_formatted_health_numbers_rejected(ref: str) -> None:
    fails = check_rows([{"invoice_ref": ref}], [], D("2026-11-10"))
    assert "phn_like" in {f.check for f in fails}


@pytest.mark.parametrize("ref", ["Smith-Jones", "Mary-Ann-Lee", "Zelda2", "OConnor", "Li-Wong3"])
def test_b1_005_name_shaped_refs_rejected(ref: str) -> None:
    fails = check_rows([{"invoice_ref": ref}], [], D("2026-11-10"))
    assert "name_like" in {f.check for f in fails}


@pytest.mark.parametrize("ref", ["INV-1001", "HV-000001", "12345", "A1B2", "2026-0042"])
def test_b1_005_invoice_shaped_refs_pass(ref: str) -> None:
    assert check_rows([{"invoice_ref": ref}], [], D("2026-11-10")) == []


def test_b1_007_unknown_payer_is_could_not_check() -> None:
    v = visit(payer="UNKNOWN", billing_code="UNMAPPED", date_of_service="2026-10-01")
    ev = run([v], on="2026-11-10")
    assert (ev.scopes[v.id].status, ev.scopes[v.id].reasons) == ("could_not_check", ("unknown_payer",))


@pytest.mark.parametrize("on,near,money_class", [
    ("2026-11-03", False, "delayed_cash"), ("2026-11-04", True, "delayed_cash"),
    ("2026-11-18", True, "delayed_cash"), ("2026-11-19", True, "permanent_certain")])
def test_reviewer_a08_wsbc02_band_edges_still_hold(on: str, near: bool, money_class: str) -> None:
    v = visit(payer="WSBC", billing_code="19102", amount_invoiced="95.00", submission_state="rejected",
              date_of_service="2026-05-01", rejected_not_before=D("2026-08-20"), rejected_by=D("2026-08-20"))
    r = result(run([v], on=on), v.id, "WSBC-02")
    assert (r.limit_date, r.near_limit, r.money_class) == (D("2026-11-18"), near, money_class)
