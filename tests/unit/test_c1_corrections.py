"""C1 corrections (2026-11-11), synthetic only.

1. Past an ICBC or WorkSafeBC submission deadline is "past payer deadline - payment at payer's discretion",
   never a loss from the date alone; "confirmed unpaid" needs the payer's recorded outcome.
3. The free audit's look-back set keeps older open invoices, so a WorkSafeBC rejection still inside its
   correction window is never dropped for being older than 90 days.
4. Rules citing the WorkSafeBC manual are version 2 (June 2026 edition, with the MOA effective 2026-04-01).
7. Three cases: timely and paid; late but paid; rejected but still correctable.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from claimcheck_api.routes import GROUP_ORDER, _group
from claimcheck_core.evidence import answers
from claimcheck_core.items import next_item
from claimcheck_core.measure import audit_figures, in_lookback_set, wsbc_correction_window_open
from claimcheck_core.outcomes import OUTCOME_STATUS
from claimcheck_core.rules.catalogue import SUPERSEDED, catalogue_versions
from claimcheck_core.rules.types import MONEY_CLASSES
from tests.fixtures.c1_cases import CASES, Case
from tests.fixtures.factories import D, result, run, visit

# ------------------------------------------------------------------ item 1


def test_icbc_past_45_days_is_payer_discretion_not_loss() -> None:
    v = visit(date_of_service="2026-10-01")
    r = result(run([v], on="2026-11-16"), v.id, "ICBC-01")
    assert (r.outcome, r.reason, r.money_class) == (
        "flag", "past_limit_payer_discretion", "past_deadline_discretionary")
    assert not (r.money_class or "").startswith("permanent")
    assert "permanent_discretionary" not in MONEY_CLASSES


def test_wsbc_past_90_days_is_payer_discretion_not_loss() -> None:
    v = visit(payer="WSBC", billing_code="19102", amount_invoiced="95.00", date_of_service="2026-07-01")
    r = result(run([v], on="2026-09-30"), v.id, "WSBC-01")
    assert (r.reason, r.money_class) == ("past_limit_payer_discretion", "past_deadline_discretionary")


def test_confirmed_unpaid_only_from_a_recorded_payer_outcome() -> None:
    v = visit(date_of_service="2026-10-01", submission_state="submitted", state_date=D("2026-11-20"))
    on = "2026-11-25"
    before = result(run([v], on=on), v.id, "ICBC-07")
    assert before.money_class == "past_deadline_discretionary"  # the date alone never confirms a loss
    declined = replace(v, portal_status="payer_declined")
    ev = run([declined], on=on)
    r = result(ev, v.id, "ICBC-01")
    assert (r.outcome, r.reason, r.money_class, r.amount) == (
        "flag", "payer_declined", "confirmed_unpaid", Decimal("97.00"))
    assert result(ev, v.id, "ICBC-07").outcome == "clear"  # one line per visit, not two
    paid_later = replace(declined, submission_state="paid", amount_paid=Decimal("97.00"))
    assert result(run([paid_later], on=on), v.id, "ICBC-01").outcome == "clear"
    assert OUTCOME_STATUS["payer_declined"] == "open"


def test_item_class_moves_from_discretion_to_confirmed_unpaid() -> None:
    v = visit(date_of_service="2026-10-01")
    r1 = result(run([v], on="2026-11-16"), v.id, "ICBC-01")
    item, _ = next_item(None, r1, D("2026-11-16"))
    assert item is not None and item.class_at_first_flag == "past_deadline_discretionary"
    r2 = result(run([replace(v, portal_status="payer_declined")], on="2026-11-23"), v.id, "ICBC-01")
    item2, events = next_item(item, r2, D("2026-11-23"))
    assert item2 is not None and item2.money_class == "confirmed_unpaid" and "class_changed" in events


def test_list_groups_separate_discretion_confirmed_and_lost() -> None:
    def g(cls: str) -> str:
        return _group(SimpleNamespace(money_class=cls, limit_date=None), D("2026-11-11"))  # type: ignore[arg-type]
    assert g("past_deadline_discretionary") == "past_deadline_payer_discretion"
    assert g("confirmed_unpaid") == "confirmed_unpaid"
    assert g("permanent_certain") == "lost"
    assert "probably_lost" not in GROUP_ORDER


def test_audit_cohort_keeps_discretion_and_confirmed_off_the_certain_line() -> None:
    audit = D("2026-12-01")
    late = visit(date_of_service=audit - timedelta(days=60))
    declined = replace(visit(date_of_service=audit - timedelta(days=55)), portal_status="payer_declined")
    fig = audit_figures(run([late, declined], on=audit), [late, declined], audit)
    c = fig.icbc_cohort
    assert (c.certain_balance, c.past_deadline_balance, c.confirmed_unpaid_balance) == (
        Decimal("0.00"), Decimal("97.00"), Decimal("97.00"))


# ------------------------------------------------------------------ item 3


def test_lookback_set_keeps_old_open_wsbc_rejection_still_correctable() -> None:
    audit = D("2026-12-01")
    # Service 200 days before the audit (older than 90 and older than 180), first seen rejected 30 days
    # before the audit: PR-08 limit is at least first rejection + 90 - so still correctable.
    old_rejected = visit(payer="WSBC", billing_code="19102", amount_invoiced="95.00",
                         date_of_service=audit - timedelta(days=200), submission_state="rejected",
                         rejected_not_before=audit - timedelta(days=40), rejected_by=audit - timedelta(days=30))
    old_paid = visit(payer="WSBC", billing_code="19102", amount_invoiced="95.00", amount_paid="95.00",
                     date_of_service=audit - timedelta(days=120), submission_state="paid")
    recent = visit(date_of_service=audit - timedelta(days=20), submission_state="paid", amount_paid="97.00")
    assert in_lookback_set(old_rejected, audit) and wsbc_correction_window_open(old_rejected, audit)
    assert not in_lookback_set(old_paid, audit)
    assert in_lookback_set(recent, audit)
    vs = [old_rejected, old_paid, recent]
    ev = run(vs, on=audit)
    r = result(ev, old_rejected.id, "WSBC-02")
    assert (r.outcome, r.money_class, r.limit_date) == ("flag", "delayed_cash", audit + timedelta(days=50))
    fig = audit_figures(ev, vs, audit)
    lb = fig.lookback
    assert (lb.in_window, lb.older_open, lb.older_wsbc_correctable, lb.excluded) == (1, 1, 1, 1)


def test_lookback_closed_window_is_still_listed_but_not_correctable() -> None:
    audit = D("2026-12-01")
    v = visit(payer="WSBC", billing_code="19102", amount_invoiced="95.00",
              date_of_service=D("2026-04-10"), submission_state="rejected", rejected_by=D("2026-05-01"))
    assert in_lookback_set(v, audit) and not wsbc_correction_window_open(v, audit)


# ------------------------------------------------------------------ item 4


def test_wsbc_manual_rules_cite_june_2026_edition_as_version_2() -> None:
    src19 = [v for v in catalogue_versions() if v.source_id == "SRC-19"]
    assert {v.rule_code for v in src19} == {"WSBC-01", "WSBC-02", "WSBC-03", "WSBC-04", "WSBC-07", "WSBC-10"}
    for v in src19:
        assert v.version == 2 and "June 2026" in v.source_citation and "2026-04-01" in v.source_citation
        assert (v.rule_code, 1) in SUPERSEDED
    w2 = next(v for v in src19 if v.rule_code == "WSBC-02")
    assert w2.params == {"service_limit_days": 180, "rejection_limit_days": 90, "near_limit_days": 14}


# ------------------------------------------------------------------ item 7


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_c1_cases_export_answers_and_portal_questions(case: Case) -> None:
    ev = run([case.visit], on=case.on)
    for rule, (outcome, cls) in case.expect.items():
        r = result(ev, case.visit.id, rule)
        assert (r.outcome, r.money_class) == (outcome, cls), (case.name, rule, r)
    got = answers(case.visit, case.on)
    assert {q: got[q].source for q in case.sources} == case.sources
    if case.visit.submission_state in ("submitted", "unsubmitted"):
        assert got["payer_accepted"].source == "portal"  # Jane's "Submitted" proves neither receipt nor payment
