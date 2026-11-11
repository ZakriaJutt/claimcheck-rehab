"""Plausibility checks on a whole batch (TRD "Import handling" step 3, checks i-iv; UT-15, IT-09, IT-18).

What the guard does and does not do: it catches a shifted column of health numbers, one-word surnames,
heavily repeated patient numbers or adult birth dates. It CANNOT prove that a value is not an
identifier: a patient-number column with few repeats in a small file, or a child's birth date in a
date field, would pass (finding F-005). The same checks are re-run daily over stored rows by
identifier_scan.

Check (i), interim: the BC personal health number check-digit algorithm must come from the Ministry of
Health's specification (T-1.1.4), which was not available in B1. Until then the guard rejects every
invoice_ref that, with hyphens removed, contains a run of ten or more digits (fix round 1, B1-006:
"9123-456-782", "P9123456782" and "9123456782-1" are caught). This is stricter than the specified check
for every value the contract's pattern admits. A genuine Jane invoice number with ten or more digits
would be refused too; T-0.1.2 records Jane's real format.

Check (ii), fix round 1 (B1-005): an invoice_ref whose digits are fewer than half of its letters and
digits is refused as name-shaped. This catches one-word surnames, hyphenated or multi-part surnames
("Smith-Jones", "Mary-Ann-Lee") and a name with a digit appended ("Zelda2"). Residual risk, stated: a
column of patient numbers, or any mostly-numeric identifier other than a health number, still passes.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from claimcheck_core.dates import add_days

TEN_DIGIT_RUN = re.compile(r"\d{10,}")
EARLIEST = date(2015, 1, 1)
DATE_FIELDS = ("date_of_service", "state_date", "end_date", "next_appointment_date", "date_of_event")
MIN_DISTINCT_SHARE = 0.5


def phn_like(ref: str) -> bool:
    return TEN_DIGIT_RUN.search(ref.replace("-", "")) is not None


def name_like(ref: str) -> bool:
    letters = sum(1 for c in ref if c.isalpha())
    digits = sum(1 for c in ref if c.isdigit())
    return digits * 2 < letters + digits


@dataclass(frozen=True)
class GuardFailure:
    check: str  # phn_like | name_like | low_distinct | date_out_of_range
    field: str
    rows: int  # how many rows tripped it (a count, never a value)


def check_rows(visits: Iterable[dict[str, Any]], claims: Iterable[dict[str, Any]], today: date) -> list[GuardFailure]:
    visits = list(visits)
    claims = list(claims)
    out: list[GuardFailure] = []
    refs = [r["invoice_ref"] for r in visits if r.get("invoice_ref")]
    n = sum(1 for r in refs if phn_like(r))
    if n:
        out.append(GuardFailure("phn_like", "invoice_ref", n))
    n = sum(1 for r in refs if name_like(r))
    if n:
        out.append(GuardFailure("name_like", "invoice_ref", n))
    if refs and len(set(refs)) / len(refs) < MIN_DISTINCT_SHARE:
        out.append(GuardFailure("low_distinct", "invoice_ref", len(refs) - len(set(refs))))
    three_years = add_days(today, -3 * 365 - 1)
    ten_years = add_days(today, -10 * 365 - 3)
    for f in DATE_FIELDS:
        bad = 0
        for r in (*visits, *claims):
            d = r.get(f)
            if d is None:
                continue
            if d < EARLIEST:
                bad += 1
            elif f == "date_of_service" and not (three_years <= d <= today):
                bad += 1
            elif f == "date_of_event" and not (ten_years <= d <= today):
                bad += 1
            elif f == "state_date" and d > today:
                bad += 1
        if bad:
            out.append(GuardFailure("date_out_of_range", f, bad))
    return out
