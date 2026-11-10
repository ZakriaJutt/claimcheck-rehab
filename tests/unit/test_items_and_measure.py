"""UT-10 (near-limit date written once, class transitions), item confirmation rules, and the
Decision.md 11.3 monthly conversions."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from claimcheck_core.items import ItemState, next_item
from claimcheck_core.measure import (
    NearLimitEntry,
    audit_figures,
    near_limit_monthly,
    nothing_needs_action_sentence,
)
from tests.fixtures.factories import D, claim, result, run, visit

SERVICE = D("2026-10-01")


def _step(item: ItemState | None, v: object, day: int) -> tuple[ItemState | None, list[str]]:
    on = SERVICE + timedelta(days=day)
    r = result(run([v], on=on), v.id, "ICBC-01")  # type: ignore[attr-defined]
    return next_item(item, r, on, v)  # type: ignore[arg-type]


def test_ut10_near_limit_written_once_on_day_31() -> None:
    v = visit(date_of_service=SERVICE)
    item, ev = _step(None, v, 13)
    assert item is None and ev == []
    item, ev = _step(item, v, 14)
    assert item is not None and ev == ["flagged"] and item.reached_near_limit_on is None
    item, _ = _step(item, v, 30)
    assert item is not None and item.reached_near_limit_on is None
    item, _ = _step(item, v, 31)
    assert item is not None and item.reached_near_limit_on == SERVICE + timedelta(days=31)
    item, _ = _step(item, v, 40)
    assert item is not None and item.reached_near_limit_on == SERVICE + timedelta(days=31)
    item, ev = _step(item, v, 46)  # limit + 1: class changes that day (MH-04 c)
    assert item is not None and item.money_class == "permanent_discretionary" and "class_changed" in ev
    assert item.class_at_first_flag == "delayed_cash" and item.first_flagged_on == SERVICE + timedelta(days=14)


def test_ut10_submitted_on_day_20_never_near_limit() -> None:
    v = visit(date_of_service=SERVICE)
    item, _ = _step(None, v, 14)
    submitted = visit(id=v.id, invoice_ref=v.invoice_ref, date_of_service=SERVICE, submission_state="submitted")
    for day in (20, 31, 44):
        item, _ = _step(item, submitted, day)
        assert item is not None and item.reached_near_limit_on is None
        assert item.status == "open"  # Jane's mark does not clear or confirm the ICBC item


def test_awaiting_confirmation_icbc_needs_payment_or_portal() -> None:
    v = visit(date_of_service=SERVICE, submission_state="partly_paid", amount_paid="0.00")
    item = ItemState("ICBC-01", "awaiting_confirmation", "delayed_cash", Decimal("97.00"), D("2026-11-15"),
                     D("2026-10-15"), "delayed_cash")
    r = result(run([v], on="2026-10-20"), v.id, "ICBC-01")
    assert r.outcome == "clear"
    same, ev = next_item(item, r, D("2026-10-20"), v, export_newer_than_outcome=True)
    assert same is not None and same.status == "awaiting_confirmation" and ev == []
    paid = visit(id=v.id, date_of_service=SERVICE, submission_state="paid", amount_paid="97.00")
    done, ev = next_item(item, r, D("2026-10-20"), paid, export_newer_than_outcome=True)
    assert done is not None and done.status == "confirmed" and ev == ["confirmed"]


def test_decision_11_3_band_example_three_standard_treatments() -> None:
    audit = D("2026-11-20")
    entries = [NearLimitEntry("ICBC-01", audit - timedelta(days=d), audit + timedelta(days=45 - d), Decimal("97.00"))
               for d in (31, 38, 45)]
    entries.append(NearLimitEntry("ICBC-01", audit - timedelta(days=30), audit, Decimal("97.00")))  # out of band
    out = near_limit_monthly(entries, audit)
    assert out.balance_by_rule["ICBC-01"] == Decimal("291.00")
    assert out.monthly_by_rule["ICBC-01"] == Decimal("582.00")
    assert out.monthly_total == Decimal("582.00")


def test_band_edges_for_each_rule() -> None:
    audit = D("2026-12-15")
    e = [NearLimitEntry("WSBC-01", audit - timedelta(days=76), audit, Decimal("95.00")),
         NearLimitEntry("WSBC-01", audit - timedelta(days=91), audit, Decimal("95.00")),
         NearLimitEntry("WSBC-02", D("2026-06-01"), audit + timedelta(days=14), Decimal("57.00")),
         NearLimitEntry("WSBC-02", D("2026-06-01"), audit + timedelta(days=15), Decimal("57.00"))]
    out = near_limit_monthly(e, audit)
    assert out.balance_by_rule == {"ICBC-01": Decimal("0.00"), "WSBC-01": Decimal("95.00"),
                                   "WSBC-02": Decimal("57.00")}
    assert out.monthly_total == Decimal("304.00")


def test_audit_figures_keep_lines_separate() -> None:
    audit = D("2026-12-01")
    c = claim(date_of_event=D("2026-06-01"))
    lost_discretionary = visit(date_of_service=audit - timedelta(days=60))
    lost_certain = visit(claim_id=c.id, date_of_service=audit - timedelta(days=50))  # after crash + 84
    near = visit(date_of_service=audit - timedelta(days=35))
    ev = run([lost_discretionary, lost_certain, near], [c], on=audit)
    fig = audit_figures(ev, [lost_discretionary, lost_certain, near], audit)
    assert fig.permanent_icbc.discretionary_balance == Decimal("97.00")
    assert fig.permanent_icbc.certain_balance == Decimal("97.00")  # not also counted as discretionary
    assert fig.permanent_icbc.discretionary_monthly == Decimal("64.67")
    assert fig.near_limit.monthly_by_rule["ICBC-01"] == Decimal("194.00")


def test_nothing_needs_action_always_carries_counts() -> None:
    s = nothing_needs_action_sentence(970, 43, 171)
    assert "970" in s and "43 could not be checked" in s and "171 had no rules applied" in s
