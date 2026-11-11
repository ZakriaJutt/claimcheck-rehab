"""C1 (2026-11-11) synthetic cases: timely and paid; late but paid; rejected but still correctable.

Every value is made up. Each case lists what the export answers and what needs the payer's portal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from claimcheck_core.evidence import Source
from claimcheck_core.rules.types import VisitIn
from tests.fixtures.factories import D, visit


@dataclass(frozen=True)
class Case:
    name: str
    visit: VisitIn
    on: date
    # rule -> (outcome, money_class or None)
    expect: dict[str, tuple[str, str | None]]
    # question -> where the answer comes from
    sources: dict[str, Source] = field(default_factory=dict)


def _v(**kw: Any) -> VisitIn:
    return visit(**kw)


TIMELY_AND_PAID = Case(
    "timely and paid",
    _v(invoice_ref="C1-00001", date_of_service=D("2026-09-29"), submission_state="paid",
       amount_paid="97.00", state_date=D("2026-10-20")),
    D("2026-11-11"),
    {"ICBC-01": ("clear", None), "ICBC-07": ("clear", None)},
    {"paid": "export", "payer_accepted": "export", "submitted_by_deadline": "portal"},
)

# Service 2026-08-03: ICBC limit 2026-09-17. Jane's export of 2026-10-01 dates the "Submitted" mark
# 2026-09-25, after the limit, unpaid: payment at ICBC's discretion, not a loss. ICBC paid on 2026-10-15.
LATE_BEFORE_PAYMENT = Case(
    "late, before payment",
    _v(invoice_ref="C1-00002", date_of_service=D("2026-08-03"), submission_state="submitted",
       state_date=D("2026-09-25")),
    D("2026-10-01"),
    {"ICBC-01": ("not_evaluated", None), "ICBC-07": ("flag", "past_deadline_discretionary")},
    {"paid": "portal", "payer_accepted": "portal", "submitted_by_deadline": "portal"},
)
LATE_BUT_PAID = Case(
    "late but paid",
    _v(invoice_ref="C1-00002", date_of_service=D("2026-08-03"), submission_state="paid",
       amount_paid="97.00", state_date=D("2026-10-15")),
    D("2026-11-11"),
    {"ICBC-01": ("clear", None), "ICBC-07": ("clear", None)},
    {"paid": "export", "payer_accepted": "export", "submitted_by_deadline": "portal"},
)

# WorkSafeBC, service 2026-05-20 (175 days before 2026-11-11: outside a "last 90 days" export). First
# seen rejected on 2026-10-01. PR-08 limit: earliest possible service + 180 = 2026-11-16; latest
# possible 2026-10-01 + 90 = 2026-12-30.
_REJECTED = dict(invoice_ref="C1-00003", payer="WSBC", billing_code="19102", amount_invoiced="95.00",
                 date_of_service=D("2026-05-20"), submission_state="rejected", rejected_by=D("2026-10-01"))
REJECTED_STILL_CORRECTABLE = Case(
    "rejected but still correctable",
    _v(**_REJECTED),
    D("2026-11-11"),
    {"WSBC-02": ("flag", "delayed_cash")},
    {"paid": "export", "payer_accepted": "export", "first_rejection_date": "portal", "correctable": "export"},
)
REJECTED_CHECK_PORTAL = Case(
    "rejected, past the earliest possible limit",
    _v(**_REJECTED),
    D("2026-11-20"),
    {"WSBC-02": ("flag", "delayed_cash")},
    {"first_rejection_date": "portal", "correctable": "portal"},
)

CASES = (TIMELY_AND_PAID, LATE_BEFORE_PAYMENT, LATE_BUT_PAID, REJECTED_STILL_CORRECTABLE, REJECTED_CHECK_PORTAL)
