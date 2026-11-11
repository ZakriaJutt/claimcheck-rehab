"""What a Jane export can answer about one visit, and what only the payer's portal can (C1, 2026-11-11).

Pure; no database. Used by the audit report and the C1 fixtures so that the product never presents a
portal fact as an export fact:

- Jane's "Submitted" is a manual mark (ICBC) or a Teleplan send (WorkSafeBC). It does not prove that the
  payer accepted the invoice, nor that it will pay. Only a recorded payment does.
- The 16 fields carry one state date (the last change), not the original submission date or the first
  rejection date (schema.md section 2). Those come from ICBC's portal (HCPP) or WorkSafeBC's Teleplan /
  My Provider Services records.
- Past a payer deadline the export cannot say whether the payer will still pay (ICBC guide s. 6.1: "may
  not be paid", at ICBC's discretion); only the payer's outcome can.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from claimcheck_core.money import ZERO
from claimcheck_core.rules.payer_rules import submission_limit, wsbc_correction_bounds
from claimcheck_core.rules.types import VisitIn

Source = Literal["export", "portal"]

ICBC_LIMIT_DAYS = 45  # PR-01
WSBC_LIMIT_DAYS = 90  # PR-07


@dataclass(frozen=True)
class Answer:
    question: str
    source: Source  # "export": the export settles it; "portal": staff must confirm with the payer
    value: str  # what the export shows, or why the portal is needed


def answers(v: VisitIn, on: date) -> dict[str, Answer]:
    """One answer per question: paid, payer_accepted, submitted_by_deadline and, for a WorkSafeBC
    rejection, first_rejection_date and correctable."""
    out: dict[str, Answer] = {}
    paid = v.amount_paid > ZERO or v.submission_state == "paid"
    portal = "ICBC's portal (HCPP)" if v.payer == "ICBC" else "Teleplan / My Provider Services"

    if paid:
        out["paid"] = Answer("paid", "export", f"paid {v.amount_paid}")
    elif v.payer == "WSBC" and v.submission_state == "rejected":
        out["paid"] = Answer("paid", "export", "rejected by WorkSafeBC (remittance), not paid")
    else:
        # Jane records ICBC payments by hand and WorkSafeBC payments from remittances: "no payment
        # recorded" is not the payer's refusal.
        out["paid"] = Answer("paid", "portal", f"no payment recorded in Jane; outcome only in {portal}")

    if paid:
        out["payer_accepted"] = Answer("payer_accepted", "export", "a payment proves the payer accepted it")
    elif v.payer == "WSBC" and v.submission_state == "rejected":
        out["payer_accepted"] = Answer("payer_accepted", "export", "rejected (remittance)")
    else:
        out["payer_accepted"] = Answer(
            "payer_accepted", "portal", f"Jane's '{v.submission_state}' does not prove receipt; check {portal}")

    limit, _ = submission_limit(v.date_of_service, ICBC_LIMIT_DAYS if v.payer == "ICBC" else WSBC_LIMIT_DAYS)
    if v.submission_state == "unsubmitted":
        out["submitted_by_deadline"] = Answer(
            "submitted_by_deadline", "export",
            "not submitted; deadline passed" if on > limit else f"not submitted; limit {limit.isoformat()}")
    else:
        note = "irrelevant once paid" if paid else "needed: payment after the limit is at the payer's discretion"
        out["submitted_by_deadline"] = Answer(
            "submitted_by_deadline", "portal", f"original submission date is not an export field ({note})")

    if v.payer == "WSBC" and v.submission_state == "rejected":
        earliest, latest = wsbc_correction_bounds(v.date_of_service, v.rejected_not_before, v.rejected_by)
        out["first_rejection_date"] = Answer(
            "first_rejection_date", "portal", "not an export field; the export gives only bounds")
        if on <= earliest:
            out["correctable"] = Answer("correctable", "export", f"yes, at least until {earliest.isoformat()}")
        elif latest is not None and on > latest:
            out["correctable"] = Answer("correctable", "export", f"no, latest possible limit {latest.isoformat()}")
        else:
            out["correctable"] = Answer(
                "correctable", "portal", "between the earliest and latest possible limit: confirm the first "
                "rejection date")
    return out
