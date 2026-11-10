"""UT-09 determinism (Hypothesis) and the HCF-1 invariant over random rows."""

from __future__ import annotations

import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from claimcheck_core.rules.engine import evaluate
from claimcheck_core.rules.types import ClaimIn, VisitIn
from tests.fixtures.factories import VERSIONS

CODES = ["ICBC-IV", "ICBC-ST", "ICBC-HT30", "UNMAPPED", "19100", "19102", "19107", "19108", "19105", "19999"]
STATES = ["unsubmitted", "submitted", "rejected", "partly_paid", "paid", "unknown"]


@st.composite
def rowsets(draw: st.DrawFn) -> tuple[list[VisitIn], list[ClaimIn], date]:
    n_claims = draw(st.integers(0, 4))
    claims = [ClaimIn(id=uuid.UUID(int=i + 1), payer=draw(st.sampled_from(["ICBC", "WSBC"])),
                      treatments_count=draw(st.none() | st.integers(0, 40)),
                      policy_max=draw(st.none() | st.integers(10, 40)),
                      date_of_event=draw(st.none() | st.dates(date(2026, 1, 1), date(2026, 11, 1))),
                      end_date=draw(st.none() | st.dates(date(2026, 3, 1), date(2027, 3, 1))),
                      policy_status=draw(st.none() | st.sampled_from(["open", "closed"])),
                      next_appointment_date=draw(st.none() | st.dates(date(2026, 4, 1), date(2027, 1, 1))))
              for i in range(n_claims)]
    visits = []
    for i in range(draw(st.integers(1, 12))):
        payer = draw(st.sampled_from(["ICBC", "WSBC", "OTHER"]))
        visits.append(VisitIn(
            id=uuid.UUID(int=1000 + i), invoice_ref=f"S-{i:04d}", payer=payer,
            discipline=draw(st.sampled_from(["physiotherapy", "support", "other"])),
            date_of_service=draw(st.dates(date(2026, 2, 1), date(2026, 11, 9))),
            billing_code=draw(st.sampled_from(CODES)),
            amount_invoiced=Decimal(draw(st.integers(0, 200))).quantize(Decimal("0.01")),
            amount_paid=Decimal(draw(st.integers(0, 200))).quantize(Decimal("0.01")),
            submission_state=draw(st.sampled_from(STATES)),
            claim_id=draw(st.none() | st.sampled_from([c.id for c in claims])) if claims else None,
            portal_status=draw(st.sampled_from([None, "not_received", "verified"])),
        ))
    on = draw(st.dates(date(2026, 4, 1), date(2027, 2, 1)))
    return visits, claims, on


def _key(ev: object) -> list[tuple[object, ...]]:
    return sorted((f.target, str(f.target_id), f.result.rule_code, f.result.outcome, f.result.reason,
                   f.result.limit_date, f.result.money_class, f.result.amount) for f in ev.findings)  # type: ignore[attr-defined]


@settings(max_examples=150, deadline=None)
@given(rowsets(), st.randoms(use_true_random=False))
def test_ut09_same_rows_any_order_identical_findings(data: tuple[list[VisitIn], list[ClaimIn], date],
                                                      rnd: random.Random) -> None:
    visits, claims, on = data
    first = evaluate(visits, claims, VERSIONS, on)
    shuffled = visits[:]
    rnd.shuffle(shuffled)
    second = evaluate(shuffled, list(reversed(claims)), list(reversed(VERSIONS)), on)
    assert _key(first) == _key(second)
    assert first.scopes == second.scopes


@settings(max_examples=150, deadline=None)
@given(rowsets())
def test_hcf1_no_clear_outside_scope(data: tuple[list[VisitIn], list[ClaimIn], date]) -> None:
    visits, claims, on = data
    ev = evaluate(visits, claims, VERSIONS, on)
    for f in ev.findings:
        if f.target == "visit":
            scope = ev.scopes[f.target_id]
            assert scope.status != "no_rules_applied"
            if scope.status == "could_not_check":
                assert f.result.outcome != "clear"
        if f.result.outcome == "not_evaluated":
            assert f.result.reason
    assert sum(ev.counts().values()) == len(visits)  # every visit is counted somewhere
    for v in visits:  # a Jane-submitted unpaid ICBC invoice never reads clear on ICBC-01
        if (v.payer == "ICBC" and v.submission_state == "submitted" and v.amount_paid == 0
                and v.portal_status is None):
            r = [f.result for f in ev.findings if f.target_id == v.id and f.result.rule_code == "ICBC-01"]
            assert all(x.outcome != "clear" for x in r)


def test_dates_are_calendar_days() -> None:
    assert date(2026, 10, 1) + timedelta(days=45) == date(2026, 11, 15)  # crosses the DST change
