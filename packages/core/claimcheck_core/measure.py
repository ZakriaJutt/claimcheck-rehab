"""Measurement figures kept on separate lines, never added together (CLAUDE.md; Decision.md 11.3).

- Near-limit delayed cash per month: per rule, the collectable balance of near-limit items whose
  service date (or correction limit) lies in that rule's 15-day band on the audit date, divided by
  the band length in months (15 / 30 = 0.5), then summed. All three are delayed cash.
- Permanent loss per month (ICBC): service dates 90 to 46 days before the audit, divided by 1.5;
  certain (PR-03) and discretionary (PR-01 passed unsubmitted) on separate lines.
- WorkSafeBC amounts already past PR-07 or PR-08: a balance, no monthly conversion.
- The "nothing needs action" sentence never appears without the not-checked counts (MH-05 e).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from claimcheck_core.dates import days_since
from claimcheck_core.money import ZERO, cad
from claimcheck_core.rules.types import Evaluation, VisitIn

DAYS_PER_MONTH = Decimal(30)  # [A] Decision.md 11.3
BAND_DAYS = Decimal(15)
BAND_MONTHS = BAND_DAYS / DAYS_PER_MONTH  # 0.5
PERMANENT_COHORT_MONTHS = Decimal("1.5")

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
class PermanentLossMonthly:
    certain_balance: Decimal
    discretionary_balance: Decimal
    certain_monthly: Decimal
    discretionary_monthly: Decimal


@dataclass
class AuditFigures:
    near_limit: NearLimitMonthly
    permanent_icbc: PermanentLossMonthly
    wsbc_past_limit_balance: Decimal  # no monthly conversion; does not enter the test


def audit_figures(evaluation: Evaluation, visits: list[VisitIn], audit_date: date) -> AuditFigures:
    by_id: dict[uuid.UUID, VisitIn] = {v.id: v for v in visits}
    entries: list[NearLimitEntry] = []
    certain: dict[uuid.UUID, Decimal] = {}
    discretionary: dict[uuid.UUID, Decimal] = {}
    wsbc_past = ZERO
    for f in evaluation.findings:
        r = f.result
        if f.target != "visit" or r.outcome != "flag":
            continue
        v = by_id[f.target_id]
        amount = r.amount or ZERO
        if r.rule_code in BANDS and r.money_class == "delayed_cash" and r.near_limit and r.limit_date:
            entries.append(NearLimitEntry(r.rule_code, v.date_of_service, r.limit_date, amount))
        age = days_since(v.date_of_service, audit_date)
        if v.payer == "ICBC" and 46 <= age <= 90:
            if r.rule_code == "ICBC-03" and r.money_class == "permanent_certain":
                certain[v.id] = amount
            elif r.rule_code == "ICBC-01" and r.money_class == "permanent_discretionary":
                discretionary[v.id] = amount
        if r.rule_code in ("WSBC-01", "WSBC-02") and r.money_class.startswith("permanent"):  # type: ignore[union-attr]
            wsbc_past += amount
    for vid in certain:  # certain wins; never count one visit on both lines
        discretionary.pop(vid, None)
    c_bal = cad(sum(certain.values(), ZERO))
    d_bal = cad(sum(discretionary.values(), ZERO))
    return AuditFigures(
        near_limit=near_limit_monthly(entries, audit_date),
        permanent_icbc=PermanentLossMonthly(
            c_bal, d_bal, cad(c_bal / PERMANENT_COHORT_MONTHS), cad(d_bal / PERMANENT_COHORT_MONTHS)
        ),
        wsbc_past_limit_balance=cad(wsbc_past),
    )


def nothing_needs_action_sentence(checked: int, could_not_check: int, no_rules_applied: int) -> str:
    """The only way the product says there is nothing to do: always with both counts (MH-05 e)."""
    return (
        f"Nothing needs action from the {checked} visits checked. "
        f"{could_not_check} could not be checked and {no_rules_applied} had no rules applied; "
        "these are not cleared."
    )
