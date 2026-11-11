"""Counts and the could-not-check list for the week view (MH-03 e, MH-05 e; B1-001, B1-002).

Every row of the latest completed export is accounted for exactly once:
visit rows = checked + rules not evaluated + could not check + no rules applied + pending
             + unreadable + repeated;
claim rows = accepted + unreadable + repeated;
and visit rows + claim rows = rows received. Visits seen only in earlier exports are counted
separately and are still evaluated. "Nothing needs action" may be said only when no row or visit
anywhere is unreadable, pending, could not be checked, or has a rule not evaluated, and no item is open.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from claimcheck_core.measure import nothing_needs_action_sentence
from claimcheck_core.models import ImportBatch, ImportRow, Visit

NOT_CHECKED = ("rules_not_evaluated", "could_not_check")
VISIT_BUCKETS = ("checked", "rules_not_evaluated", "could_not_check", "no_rules_applied", "pending",
                 "unreadable", "repeated")
_STATUS_BUCKET = {"in_scope": "checked", "rules_not_evaluated": "rules_not_evaluated",
                  "could_not_check": "could_not_check", "no_rules_applied": "no_rules_applied", None: "pending"}


@dataclass
class WeekCounts:
    latest_batch_id: str | None = None
    rows_received: int = 0
    visits: dict[str, int] = field(default_factory=lambda: dict.fromkeys(VISIT_BUCKETS, 0))
    claims: dict[str, int] = field(default_factory=lambda: {"accepted": 0, "unreadable": 0, "repeated": 0})
    earlier_exports: dict[str, int] = field(default_factory=lambda: dict.fromkeys(VISIT_BUCKETS[:5], 0))
    not_checked_rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def adds_up(self) -> bool:
        return sum(self.visits.values()) + sum(self.claims.values()) == self.rows_received

    @property
    def not_checked_total(self) -> int:
        v, e = self.visits, self.earlier_exports
        return (v["rules_not_evaluated"] + v["could_not_check"] + v["unreadable"] + self.claims["unreadable"]
                + e["rules_not_evaluated"] + e["could_not_check"])

    @property
    def pending_total(self) -> int:
        return self.visits["pending"] + self.earlier_exports["pending"]

    def as_dict(self) -> dict[str, Any]:
        return {"latest_batch_id": self.latest_batch_id, "rows_received": self.rows_received,
                "visits": self.visits, "claims": self.claims, "earlier_exports": self.earlier_exports,
                "not_checked_total": self.not_checked_total, "adds_up": self.adds_up}


def week_counts(s: Session) -> WeekCounts:
    out = WeekCounts()
    visits = {(v.invoice_ref, v.line_no): v for v in s.scalars(select(Visit))}
    latest = s.scalars(select(ImportBatch).where(ImportBatch.status.in_(("completed", "completed_with_rejects")))
                       .order_by(ImportBatch.export_date.desc(), ImportBatch.created_at.desc())).first()
    in_latest: set[Any] = set()
    if latest is not None:
        out.latest_batch_id = str(latest.id)
        out.rows_received = latest.rows_received
        for r in s.scalars(select(ImportRow).where(ImportRow.batch_id == latest.id)
                           .order_by(ImportRow.kind, ImportRow.row_no)):
            p = r.payload
            if r.kind == "claim":
                out.claims["accepted" if r.reject_reason is None else
                           "repeated" if r.reject_reason == "duplicate_row" else "unreadable"] += 1
                if r.reject_reason not in (None, "duplicate_row"):
                    out.not_checked_rows.append({"kind": "claim", "row_no": r.row_no, "invoice_ref": None,
                                                 "reason": f"row:{r.reject_reason}"})
                continue
            if r.reject_reason == "duplicate_row":
                out.visits["repeated"] += 1
            elif r.reject_reason is not None:
                out.visits["unreadable"] += 1
                out.not_checked_rows.append({"kind": "visit", "row_no": r.row_no,
                                             "invoice_ref": p.get("invoice_ref"),
                                             "reason": f"row:{r.reject_reason}"})
            else:
                v = visits.get((p["invoice_ref"], p.get("line_no", 1)))
                if v is None:  # accepted rows always have a visit; never let one vanish
                    out.visits["pending"] += 1
                    continue
                in_latest.add(v.id)
                out.visits[_STATUS_BUCKET[v.check_status]] += 1
    for v in visits.values():
        if v.id not in in_latest:
            out.earlier_exports[_STATUS_BUCKET[v.check_status]] += 1
    for v in sorted((v for v in visits.values() if v.check_status in NOT_CHECKED),
                    key=lambda v: (v.date_of_service, v.invoice_ref, v.line_no)):
        out.not_checked_rows.append({"kind": "visit", "visit_id": str(v.id), "invoice_ref": v.invoice_ref,
                                     "payer": v.payer, "date_of_service": v.date_of_service.isoformat(),
                                     "reason": v.check_reason, "status": v.check_status})
    return out


def reasons(c: WeekCounts) -> dict[str, int]:
    return dict(Counter(r["reason"] for r in c.not_checked_rows))


def summary_sentence(c: WeekCounts, open_items: int, evaluated: bool) -> str | None:
    if (not evaluated or c.latest_batch_id is None or open_items or c.not_checked_total or c.pending_total
            or not c.adds_up):
        return None
    checked = c.visits["checked"] + c.earlier_exports["checked"]
    nra = c.visits["no_rules_applied"] + c.earlier_exports["no_rules_applied"]
    return nothing_needs_action_sentence(checked, 0, nra)


def banner(c: WeekCounts) -> str | None:
    if c.not_checked_total:
        return f"{c.not_checked_total} could not be checked. They are not fine."
    if c.latest_batch_id is not None and not c.adds_up:
        return "The latest import's counts do not add up. Nothing on this list is confirmed."
    return None
