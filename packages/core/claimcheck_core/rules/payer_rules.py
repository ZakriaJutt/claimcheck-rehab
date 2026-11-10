"""ICBC-01..08 and WSBC-01..10 (TRD.md "Deterministic rules"). Pure functions; the engine picks the
version by date of service and enforces scope. Each returns flag, clear or not_evaluated(reason)
independently of every other rule (MH-03)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from claimcheck_core.dates import add_days, days_since
from claimcheck_core.money import ZERO, cad
from claimcheck_core.rules.types import (
    ICBC_INITIAL,
    ICBC_SESSION_CODES,
    R_JANE_SUBMITTED_UNVERIFIED,
    R_MISSING_DATE_OF_EVENT,
    R_MISSING_DATES,
    R_MISSING_POLICY_STATUS,
    R_MISSING_TREATMENT_COUNT,
    R_NO_CLAIM_LINK,
    R_NO_RULE_VERSION,
    R_UNKNOWN_STATE,
    R_UNMAPPED_CODE,
    UNMAPPED,
    ClaimIn,
    MoneyClass,
    Result,
    RuleVersionIn,
    VisitIn,
)


@dataclass
class Context:
    on_date: date
    claims: dict[uuid.UUID, ClaimIn] = field(default_factory=dict)
    visits_by_claim: dict[uuid.UUID, list[VisitIn]] = field(default_factory=dict)

    def claim_of(self, v: VisitIn) -> ClaimIn | None:
        return self.claims.get(v.claim_id) if v.claim_id else None

    def siblings(self, v: VisitIn) -> list[VisitIn]:
        return self.visits_by_claim.get(v.claim_id, []) if v.claim_id else []


VisitRule = Callable[[VisitIn, RuleVersionIn, Context], Result]
ClaimRule = Callable[[ClaimIn, list[VisitIn], RuleVersionIn, Context], Result]


def _ne(code: str, ver: RuleVersionIn | None, reason: str, **kw: object) -> Result:
    return Result(code, "not_evaluated", reason, ver.id if ver else None, **kw)  # type: ignore[arg-type]


def _clear(code: str, ver: RuleVersionIn, **kw: object) -> Result:
    return Result(code, "clear", None, ver.id, **kw)  # type: ignore[arg-type]


def _flag(
    code: str, ver: RuleVersionIn, reason: str, money_class: MoneyClass, amount: Decimal | None,
    limit: date | None = None, submit_by: date | None = None, near_limit: bool = False,
) -> Result:
    if money_class in ("admin_time", "warning"):
        amount = None
    return Result(code, "flag", reason, ver.id, limit, submit_by, money_class,
                  cad(amount) if amount is not None else None, near_limit)


def outstanding(v: VisitIn) -> Decimal:
    return max(cad(v.amount_invoiced - v.amount_paid), ZERO)


def _key(v: VisitIn) -> tuple[date, str, int, str]:
    return (v.date_of_service, v.invoice_ref, v.line_no, str(v.id))


# ---------------------------------------------------------------- deadline arithmetic (UT-01..03)

def submission_limit(date_of_service: date, limit_days: int) -> tuple[date, date]:
    """Payer limit and our 'submit by' (one day earlier, because neither source says whether the
    last day counts)."""
    limit = add_days(date_of_service, limit_days)
    return limit, add_days(limit, -1)


def wsbc_correction_limit(
    date_of_service: date, first_rejected_on: date | None, service_days: int = 180, rejection_days: int = 90
) -> date:
    """PR-08: later of service + 180 and first rejection + 90. Unknown first rejection date gives
    service + 180, the earliest value the rule allows (never a guessed later date)."""
    limit = add_days(date_of_service, service_days)
    if first_rejected_on is not None:
        limit = max(limit, add_days(first_rejected_on, rejection_days))
    return limit


# ---------------------------------------------------------------- ICBC visit rules

def icbc_01(v: VisitIn, ver: RuleVersionIn, ctx: Context) -> Result:
    p = ver.params
    code = "ICBC-01"
    if v.submission_state == "unknown":
        return _ne(code, ver, R_UNKNOWN_STATE)
    limit, submit_by = submission_limit(v.date_of_service, p["limit_days"])
    if v.portal_status == "not_received" or v.submission_state == "unsubmitted":
        pass  # unsubmitted (or ICBC's portal does not have it): the deadline applies
    elif (v.submission_state == "submitted" and v.amount_paid == ZERO and v.portal_status != "verified"):
        # Jane's "Submitted" is a manual mark, not proof that ICBC has the invoice: never clear here.
        # ICBC-07 carries the limit and asks for portal verification.
        return _ne(code, ver, R_JANE_SUBMITTED_UNVERIFIED, limit_date=limit, submit_by=submit_by)
    else:
        return _clear(code, ver, limit_date=limit, submit_by=submit_by)
    days = days_since(v.date_of_service, ctx.on_date)
    if days < p["flag_after_days"]:
        return _clear(code, ver, limit_date=limit, submit_by=submit_by)
    if ctx.on_date > limit:
        return _flag(code, ver, "past_limit_unsubmitted", "permanent_discretionary", outstanding(v),
                     limit, submit_by, near_limit=True)
    return _flag(code, ver, "not_invoiced", "delayed_cash", outstanding(v), limit, submit_by,
                 near_limit=days >= p["near_limit_from_day"])


def icbc_03(v: VisitIn, ver: RuleVersionIn, ctx: Context) -> Result:
    code = "ICBC-03"
    claim = ctx.claim_of(v)
    if claim is None:
        return _ne(code, ver, R_NO_CLAIM_LINK)
    if claim.date_of_event is None and claim.end_date is None:
        return _ne(code, ver, R_MISSING_DATES)
    # A recorded end date is the clinic's record of the approved period (it may extend past the
    # Early Access Period); without one, the period ends on crash date + 84 days.
    if claim.end_date is not None:
        period_end = claim.end_date
    else:
        assert claim.date_of_event is not None
        period_end = add_days(claim.date_of_event, ver.params["early_access_days"])
    if v.date_of_service > period_end:
        return _flag(code, ver, "outside_approval_period", "permanent_certain", outstanding(v), period_end)
    if claim.next_appointment_date is not None and claim.next_appointment_date > period_end:
        return _flag(code, ver, "next_visit_outside_approval_period", "warning", None, period_end)
    return _clear(code, ver, limit_date=period_end)


def _icbc_physio_siblings(v: VisitIn, ctx: Context) -> list[VisitIn]:
    return [s for s in ctx.siblings(v) if s.payer == "ICBC" and s.discipline == "physiotherapy"]


def icbc_04(v: VisitIn, ver: RuleVersionIn, ctx: Context) -> Result:
    code = "ICBC-04"
    if v.claim_id is None:
        return _ne(code, ver, R_NO_CLAIM_LINK)
    sibs = _icbc_physio_siblings(v, ctx)
    if v.billing_code == ICBC_INITIAL:
        if any(s.billing_code == ICBC_INITIAL and _key(s) < _key(v) for s in sibs):
            return _flag(code, ver, "second_initial_visit", "warning", None)
    elif v.billing_code in ICBC_SESSION_CODES:
        if any(s.billing_code == ICBC_INITIAL and s.date_of_service == v.date_of_service for s in sibs):
            return _flag(code, ver, "treatment_on_initial_visit_date", "warning", None)
    return _clear(code, ver)


def icbc_05(v: VisitIn, ver: RuleVersionIn, ctx: Context) -> Result:
    code = "ICBC-05"
    if v.claim_id is None:
        return _ne(code, ver, R_NO_CLAIM_LINK)
    sessions = ICBC_SESSION_CODES - {ICBC_INITIAL}
    if v.billing_code in sessions:
        same_day = [s for s in _icbc_physio_siblings(v, ctx)
                    if s.date_of_service == v.date_of_service and s.billing_code in sessions]
        if len(same_day) >= 2:
            return _flag(code, ver, "two_sessions_same_day", "warning", None)
    return _clear(code, ver)


def _fee_rule(code: str, v: VisitIn, ver: RuleVersionIn) -> Result:
    if v.billing_code == UNMAPPED:
        return _ne(code, ver, R_UNMAPPED_CODE)
    raw = ver.params["fees"].get(v.billing_code)
    if raw is None:
        # The code has no fee in the version for this date (e.g. Hand Therapy before 2026-09-27).
        return _ne(code, ver, R_NO_RULE_VERSION)
    fee = cad(raw)
    if v.submission_state == "paid" and v.amount_paid < fee:
        return _flag(code, ver, "paid_below_schedule", "permanent_certain", fee - v.amount_paid)
    if cad(v.amount_invoiced) != fee:
        return _flag(code, ver, "jane_setup", "admin_time", None)
    return _clear(code, ver)


def icbc_06(v: VisitIn, ver: RuleVersionIn, ctx: Context) -> Result:
    return _fee_rule("ICBC-06", v, ver)


def icbc_07(v: VisitIn, ver: RuleVersionIn, ctx: Context) -> Result:
    p = ver.params
    code = "ICBC-07"
    if v.submission_state == "unknown":
        return _ne(code, ver, R_UNKNOWN_STATE)
    limit, submit_by = submission_limit(v.date_of_service, p["limit_days"])
    if v.portal_status == "not_received":
        return _clear(code, ver)  # treated as unsubmitted: ICBC-01 applies
    if v.submission_state != "submitted" or v.amount_paid > ZERO:
        return _clear(code, ver)
    if days_since(v.date_of_service, ctx.on_date) < p["flag_after_days"]:
        return _clear(code, ver, limit_date=limit, submit_by=submit_by)
    chase_from = add_days(v.state_date or v.date_of_service, p["chase_after_days"])
    reason = "chase_payment" if ctx.on_date >= chase_from else "verify_in_portal"
    if v.portal_status == "verified" and reason == "verify_in_portal":
        return _clear(code, ver, limit_date=limit, submit_by=submit_by)
    return _flag(code, ver, reason, "delayed_cash", outstanding(v), limit, submit_by)


# ---------------------------------------------------------------- ICBC claim rules

def icbc_02(c: ClaimIn, visits: list[VisitIn], ver: RuleVersionIn, ctx: Context) -> Result:
    code = "ICBC-02"
    p = ver.params
    if c.treatments_count is None:
        return _ne(code, ver, R_MISSING_TREATMENT_COUNT)
    allowed = max(p["pre_authorized"], c.policy_max or 0)  # a raised maximum is the clinic's record
    warn_at = allowed - (p["pre_authorized"] - p["warn_at"])
    if c.treatments_count > allowed:
        return _flag(code, ver, "treatments_over_maximum", "permanent_certain", None)
    if c.treatments_count >= warn_at and c.next_appointment_date is not None:
        return _flag(code, ver, "treatments_near_maximum", "warning", None)
    return _clear(code, ver)


def icbc_08(c: ClaimIn, visits: list[VisitIn], ver: RuleVersionIn, ctx: Context) -> Result:
    if c.policy_max is None or c.end_date is None:
        return _flag("ICBC-08", ver, "no_maximum_or_end_date", "admin_time", None)
    return _clear("ICBC-08", ver)


# ---------------------------------------------------------------- WorkSafeBC visit rules

def wsbc_01(v: VisitIn, ver: RuleVersionIn, ctx: Context) -> Result:
    p = ver.params
    code = "WSBC-01"
    if v.submission_state == "unknown":
        return _ne(code, ver, R_UNKNOWN_STATE)
    limit, submit_by = submission_limit(v.date_of_service, p["limit_days"])
    if v.submission_state != "unsubmitted":
        return _clear(code, ver, limit_date=limit, submit_by=submit_by)
    days = days_since(v.date_of_service, ctx.on_date)
    if days < p["flag_after_days"]:
        return _clear(code, ver, limit_date=limit, submit_by=submit_by)
    if ctx.on_date > limit:
        return _flag(code, ver, "past_limit_unsubmitted", "permanent_discretionary", outstanding(v),
                     limit, submit_by, near_limit=True)
    return _flag(code, ver, "not_invoiced", "delayed_cash", outstanding(v), limit, submit_by,
                 near_limit=days >= p["near_limit_from_day"])


def wsbc_02(v: VisitIn, ver: RuleVersionIn, ctx: Context) -> Result:
    p = ver.params
    code = "WSBC-02"
    if v.submission_state == "unknown":
        return _ne(code, ver, R_UNKNOWN_STATE)
    if v.submission_state != "rejected":
        return _clear(code, ver)
    limit = wsbc_correction_limit(v.date_of_service, v.first_rejected_on,
                                  p["service_limit_days"], p["rejection_limit_days"])
    submit_by = add_days(limit, -1)
    if ctx.on_date > limit:
        return _flag(code, ver, "past_correction_limit", "permanent_certain", outstanding(v),
                     limit, submit_by, near_limit=True)
    near = days_since(ctx.on_date, limit) <= p["near_limit_days"]
    return _flag(code, ver, "rejected_not_corrected", "delayed_cash", outstanding(v), limit, submit_by,
                 near_limit=near)


def wsbc_03(v: VisitIn, ver: RuleVersionIn, ctx: Context) -> Result:
    if v.claim_id is None:
        return _flag("WSBC-03", ver, "no_claim_number", "delayed_cash", outstanding(v))
    return _clear("WSBC-03", ver)


def wsbc_04(v: VisitIn, ver: RuleVersionIn, ctx: Context) -> Result:
    code = "WSBC-04"
    if v.claim_id is None:
        return _ne(code, ver, R_NO_CLAIM_LINK)
    codes = set(ver.params["treatment_codes"])
    if v.billing_code not in codes:
        return _clear(code, ver)
    # Support sessions (19107, 19108) count whoever delivered them (PR-09).
    same_day = sorted((s for s in ctx.siblings(v) if s.payer == "WSBC" and s.billing_code in codes
                       and s.date_of_service == v.date_of_service), key=_key)
    if len(same_day) >= 2 and same_day[0].id != v.id:
        return _flag(code, ver, "second_visit_same_day", "permanent_certain", outstanding(v))
    return _clear(code, ver)


def wsbc_05(v: VisitIn, ver: RuleVersionIn, ctx: Context) -> Result:
    code = "WSBC-05"
    p = ver.params
    if v.billing_code != p["follow_up"]:
        return _clear(code, ver)
    if v.claim_id is None:
        return _ne(code, ver, R_NO_CLAIM_LINK)
    if any(s.billing_code in p["initial_codes"] and s.date_of_service == v.date_of_service
           for s in ctx.siblings(v) if s.payer == "WSBC"):
        return _flag(code, ver, "follow_up_with_initial", "delayed_cash", outstanding(v))
    return _clear(code, ver)


def wsbc_06(v: VisitIn, ver: RuleVersionIn, ctx: Context) -> Result:
    code = "WSBC-06"
    p = ver.params
    if v.billing_code != p["initial_code"]:
        return _clear(code, ver)
    claim = ctx.claim_of(v)
    if claim is None:
        return _ne(code, ver, R_NO_CLAIM_LINK)
    if claim.date_of_event is None:
        return _ne(code, ver, R_MISSING_DATE_OF_EVENT)
    if days_since(claim.date_of_event, v.date_of_service) > p["within_days"]:
        return _flag(code, ver, "initial_after_60_days", "warning", None)
    return _clear(code, ver)


def wsbc_08(v: VisitIn, ver: RuleVersionIn, ctx: Context) -> Result:
    return _fee_rule("WSBC-08", v, ver)


def wsbc_10(v: VisitIn, ver: RuleVersionIn, ctx: Context) -> Result:
    code = "WSBC-10"
    if v.submission_state == "unknown":
        return _ne(code, ver, R_UNKNOWN_STATE)
    if v.submission_state == "submitted" and v.amount_paid == ZERO:
        if days_since(v.state_date or v.date_of_service, ctx.on_date) >= ver.params["unpaid_days"]:
            return _flag(code, ver, "chase_payment", "delayed_cash", outstanding(v))
    return _clear(code, ver)


# ---------------------------------------------------------------- WorkSafeBC claim rules

def wsbc_07(c: ClaimIn, visits: list[VisitIn], ver: RuleVersionIn, ctx: Context) -> Result:
    code = "WSBC-07"
    p = ver.params
    treat = sorted((v for v in visits if v.billing_code in p["treatment_codes"]), key=_key)
    if not treat:
        return _clear(code, ver)
    max_visits = c.policy_max if c.policy_max and c.policy_max > p["max_visits"] else p["max_visits"]
    first, last = treat[0].date_of_service, treat[-1].date_of_service
    period_end = c.end_date if c.end_date is not None else add_days(first, p["max_days"])
    if len(treat) > max_visits:
        return _flag(code, ver, "treatment_visits_over_maximum", "warning", None, period_end)
    if last > period_end:
        return _flag(code, ver, "visit_after_treatment_period", "warning", None, period_end)
    return _clear(code, ver, limit_date=period_end)


def wsbc_09(c: ClaimIn, visits: list[VisitIn], ver: RuleVersionIn, ctx: Context) -> Result:
    code = "WSBC-09"
    p = ver.params
    if any(v.billing_code == p["report_code"] for v in visits):
        return _clear(code, ver)
    if c.policy_status is None and c.next_appointment_date is None:
        return _ne(code, ver, R_MISSING_POLICY_STATUS)
    closed = c.policy_status == "closed"
    last = max(v.date_of_service for v in visits)
    idle = c.next_appointment_date is None and days_since(last, ctx.on_date) >= p["idle_days"]
    if closed or idle:
        return _flag(code, ver, "report_fee_not_billed", "delayed_cash", cad(p["report_fee"]))
    return _clear(code, ver)


VISIT_RULES: dict[str, dict[str, VisitRule]] = {
    "ICBC": {"ICBC-01": icbc_01, "ICBC-03": icbc_03, "ICBC-04": icbc_04, "ICBC-05": icbc_05,
             "ICBC-06": icbc_06, "ICBC-07": icbc_07},
    "WSBC": {"WSBC-01": wsbc_01, "WSBC-02": wsbc_02, "WSBC-03": wsbc_03, "WSBC-04": wsbc_04,
             "WSBC-05": wsbc_05, "WSBC-06": wsbc_06, "WSBC-08": wsbc_08, "WSBC-10": wsbc_10},
}
CLAIM_RULES: dict[str, dict[str, ClaimRule]] = {
    "ICBC": {"ICBC-02": icbc_02, "ICBC-08": icbc_08},
    "WSBC": {"WSBC-07": wsbc_07, "WSBC-09": wsbc_09},
}
# Deadline and unpaid rules: for a visit that could not be checked they return not_evaluated with
# the scope reason (TRD "Scope and state come before any rule").
DEADLINE_RULES = frozenset({"ICBC-01", "ICBC-07", "WSBC-01", "WSBC-02", "WSBC-10"})
NEAR_LIMIT_RULES = frozenset({"ICBC-01", "WSBC-01", "WSBC-02"})
