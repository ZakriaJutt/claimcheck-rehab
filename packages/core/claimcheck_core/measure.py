"""Measurement figures kept on separate lines, never added together (CLAUDE.md; Decision.md 11.3).

- Near-limit delayed cash per month: per rule, the collectable balance of near-limit items whose
  service date (or correction limit) lies in that rule's 15-day band on the audit date, divided by
  the band length in months (15 / 30 = 0.5), then summed. All three are delayed cash.
- ICBC cohort per month: service dates 90 to 46 days before the audit, divided by 1.5, on three separate
  lines (C1, 2026-11-11): certain loss (PR-03: not eligible), past payer deadline with payment at ICBC's
  discretion (PR-01 passed unsubmitted; guide s. 6.1 "may not be paid"; NOT a confirmed loss), and
  confirmed unpaid (staff recorded ICBC's outcome). Which lines the stop-rule figure uses is an open owner
  decision (Decision.md section 16, OD-1); the code never adds them.
- WorkSafeBC amounts past PR-07 (payer's discretion) or past PR-08 (manual: "cannot be paid"): two
  balances, no monthly conversion.
- Look-back set of the free audit (C1): service dates in the 90 days before the audit, plus every older
  invoice still open (unsubmitted, rejected, submitted unpaid, partly paid, or in an unknown state),
  whatever its service date, so a WorkSafeBC rejection whose PR-08 correction window is still open is
  never left out because its visit is older than 90 days.
- The "nothing needs action" sentence never appears without the not-checked counts (MH-05 e).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from claimcheck_core.dates import days_since
from claimcheck_core.money import ZERO, cad
from claimcheck_core.rules.payer_rules import outstanding, wsbc_correction_bounds
from claimcheck_core.rules.types import Evaluation, VisitIn

DAYS_PER_MONTH = Decimal(30)  # [A] Decision.md 11.3
BAND_DAYS = Decimal(15)
BAND_MONTHS = BAND_DAYS / DAYS_PER_MONTH  # 0.5
PERMANENT_COHORT_MONTHS = Decimal("1.5")
LOOKBACK_DAYS = 90  # [C] "a free audit of the last 90 days"
OPEN_STATES = frozenset({"unsubmitted", "rejected", "submitted", "partly_paid", "unknown"})


def in_lookback_set(v: VisitIn, audit_date: date) -> bool:
    """C1: the free audit's look-back set. Service in the last 90 days, or an older invoice still open.
    "unknown" counts as open (it cannot be shown as settled, HCF-1)."""
    age = days_since(v.date_of_service, audit_date)
    if 0 <= age <= LOOKBACK_DAYS:
        return True
    if age < 0:
        return False
    if v.submission_state == "unknown":
        return True
    return v.submission_state in OPEN_STATES and outstanding(v) > ZERO


def wsbc_correction_window_open(v: VisitIn, audit_date: date) -> bool:
    """A WorkSafeBC rejection whose PR-08 window may still be open on the audit date: the latest possible
    limit is unknown or not yet passed (B1-010 bounds). Independent of the service date."""
    if v.payer != "WSBC" or v.submission_state != "rejected":
        return False
    _, latest = wsbc_correction_bounds(v.date_of_service, v.rejected_not_before, v.rejected_by)
    return latest is None or audit_date <= latest

# (rule, low, high): ICBC-01 / WSBC-01 bands are days since service; WSBC-02 is days until the limit.
BANDS: dict[str, tuple[int, int]] = {"ICBC-01": (31, 45), "WSBC-01": (76, 90), "WSBC-02": (0, 14)}


@dataclass(frozen=True)
class NearLimitEntry:
    rule_code: str
    date_of_service: date
    limit_date: date
    balance: Decimal


@dataclass
class NearLimitMonthly:
    balance_by_rule: dict[str, Decimal] = field(default_factory=dict)
    monthly_by_rule: dict[str, Decimal] = field(default_factory=dict)
    monthly_total: Decimal = ZERO


def in_band(entry: NearLimitEntry, audit_date: date) -> bool:
    low, high = BANDS[entry.rule_code]
    if entry.rule_code == "WSBC-02":
        n = days_since(audit_date, entry.limit_date)
    else:
        n = days_since(entry.date_of_service, audit_date)
    return low <= n <= high


def near_limit_monthly(entries: list[NearLimitEntry], audit_date: date) -> NearLimitMonthly:
    out = NearLimitMonthly()
    for rule in BANDS:
        bal = cad(sum((e.balance for e in entries if e.rule_code == rule and in_band(e, audit_date)), ZERO))
        out.balance_by_rule[rule] = bal
        out.monthly_by_rule[rule] = cad(bal / BAND_MONTHS)
    out.monthly_total = cad(sum(out.monthly_by_rule.values(), ZERO))
    return out


@dataclass
class IcbcCohortMonthly:
    """ICBC visits with service dates 90 to 46 days before the audit, three lines never added (C1)."""

    certain_balance: Decimal  # PR-03: not eligible (certain loss)
    past_deadline_balance: Decimal  # PR-01 passed: payment at ICBC's discretion, not a confirmed loss
    certain_monthly: Decimal
    past_deadline_monthly: Decimal
    confirmed_unpaid_balance: Decimal = ZERO  # ICBC's outcome recorded by staff
    confirmed_unpaid_monthly: Decimal = ZERO


@dataclass
class LookbackCounts:
    in_window: int = 0  # service date in the last 90 days
    older_open: int = 0  # older than 90 days and still open
    older_wsbc_correctable: int = 0  # of those, WorkSafeBC rejections whose PR-08 window may be open
    excluded: int = 0  # older and settled: not in the audit


@dataclass
class AuditFigures:
    near_limit: NearLimitMonthly
    icbc_cohort: IcbcCohortMonthly
    # WorkSafeBC balances, no monthly conversion; they do not enter the test.
    wsbc_past_deadline_balance: Decimal  # PR-07 passed: payment at WorkSafeBC's discretion
    wsbc_past_correction_balance: Decimal = ZERO  # past the latest possible PR-08 limit: "cannot be paid"
    # B1-010: WSBC-02 past the earliest but not the latest possible limit: at risk, may still be
    # collectable; never counted as a loss.
    wsbc_at_risk_balance: Decimal = ZERO
    lookback: LookbackCounts = field(default_factory=LookbackCounts)


def audit_figures(evaluation: Evaluation, visits: list[VisitIn], audit_date: date) -> AuditFigures:
    by_id: dict[uuid.UUID, VisitIn] = {v.id: v for v in visits}
    counts = LookbackCounts()
    scope: set[uuid.UUID] = set()
    for v in visits:
        if not in_lookback_set(v, audit_date):
            counts.excluded += 1
            continue
        scope.add(v.id)
        if days_since(v.date_of_service, audit_date) <= LOOKBACK_DAYS:
            counts.in_window += 1
        else:
            counts.older_open += 1
            if wsbc_correction_window_open(v, audit_date):
                counts.older_wsbc_correctable += 1
    entries: list[NearLimitEntry] = []
    certain: dict[uuid.UUID, Decimal] = {}
    past_deadline: dict[uuid.UUID, Decimal] = {}
    confirmed: dict[uuid.UUID, Decimal] = {}
    wsbc_discretion = ZERO
    wsbc_past_correction = ZERO
    wsbc_at_risk = ZERO
    for f in evaluation.findings:
        r = f.result
        if f.target != "visit" or r.outcome != "flag" or f.target_id not in scope:
            continue
        v = by_id[f.target_id]
        amount = r.amount or ZERO
        if r.rule_code in BANDS and r.money_class == "delayed_cash" and r.near_limit and r.limit_date:
            entries.append(NearLimitEntry(r.rule_code, v.date_of_service, r.limit_date, amount))
        age = days_since(v.date_of_service, audit_date)
        if v.payer == "ICBC" and 46 <= age <= 90:
            if r.rule_code == "ICBC-03" and r.money_class == "permanent_certain":
                certain[v.id] = amount
            elif r.rule_code in ("ICBC-01", "ICBC-07") and r.money_class == "past_deadline_discretionary":
                past_deadline[v.id] = amount
            elif r.rule_code == "ICBC-01" and r.money_class == "confirmed_unpaid":
                confirmed[v.id] = amount
        if r.rule_code == "WSBC-01" and r.money_class == "past_deadline_discretionary":
            wsbc_discretion += amount
        elif r.rule_code == "WSBC-02" and r.money_class == "permanent_certain":
            wsbc_past_correction += amount
        elif r.rule_code == "WSBC-02" and r.reason == "check_first_rejection_date":
            wsbc_at_risk += amount
    for vid in certain:  # certain wins; never count one visit on two lines
        past_deadline.pop(vid, None)
        confirmed.pop(vid, None)
    for vid in confirmed:
        past_deadline.pop(vid, None)
    c_bal = cad(sum(certain.values(), ZERO))
    d_bal = cad(sum(past_deadline.values(), ZERO))
    u_bal = cad(sum(confirmed.values(), ZERO))
    m = PERMANENT_COHORT_MONTHS
    return AuditFigures(
        near_limit=near_limit_monthly(entries, audit_date),
        icbc_cohort=IcbcCohortMonthly(c_bal, d_bal, cad(c_bal / m), cad(d_bal / m), u_bal, cad(u_bal / m)),
        wsbc_past_deadline_balance=cad(wsbc_discretion),
        wsbc_past_correction_balance=cad(wsbc_past_correction),
        wsbc_at_risk_balance=cad(wsbc_at_risk),
        lookback=counts,
    )


def nothing_needs_action_sentence(checked: int, could_not_check: int, no_rules_applied: int) -> str:
    """The only way the product says there is nothing to do: always with both counts (MH-05 e)."""
    return (
        f"Nothing needs action from the {checked} visits checked. "
        f"{could_not_check} could not be checked and {no_rules_applied} had no rules applied; "
        "these are not cleared."
    )
