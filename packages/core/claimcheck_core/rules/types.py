"""Typed inputs and outputs of the rule engine. Pure data; no database access."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

Outcome = Literal["flag", "clear", "not_evaluated"]
MoneyClass = Literal["permanent_certain", "permanent_discretionary", "delayed_cash", "admin_time", "warning"]
CheckStatus = Literal["in_scope", "rules_not_evaluated", "could_not_check", "no_rules_applied"]
PortalStatus = Literal["not_received", "verified"] | None

ICBC = "ICBC"
WSBC = "WSBC"
OTHER = "OTHER"
UNMAPPED = "UNMAPPED"
UNKNOWN_PAYER = "UNKNOWN"

# Canonical ICBC service codes produced by the export profile's billing-code map (T-1.1.2 `[A]`:
# Jane billing codes are clinic-defined; the profile maps each one to an ICBC service type).
ICBC_INITIAL = "ICBC-IV"
ICBC_STANDARD = "ICBC-ST"
ICBC_SPECIALIZED = "ICBC-SE"
ICBC_HAND_15 = "ICBC-HT15"
ICBC_HAND_30 = "ICBC-HT30"
ICBC_HAND_45 = "ICBC-HT45"
ICBC_SESSION_CODES = frozenset(
    {ICBC_INITIAL, ICBC_STANDARD, ICBC_SPECIALIZED, ICBC_HAND_15, ICBC_HAND_30, ICBC_HAND_45}
)
ICBC_KNOWN_CODES = ICBC_SESSION_CODES

# Reason codes (fixed list; no free text anywhere).
R_UNKNOWN_STATE = "unknown_state"
R_NO_RULE_VERSION = "no_rule_version"
R_UNMAPPED_CODE = "unmapped_code"
R_NO_CLAIM_LINK = "no_claim_link"
R_MISSING_DATES = "missing_dates"
R_MISSING_TREATMENT_COUNT = "missing_treatment_count"
R_MISSING_DATE_OF_EVENT = "missing_date_of_event"
R_MISSING_POLICY_STATUS = "missing_policy_status_and_next_appointment"
R_JANE_SUBMITTED_UNVERIFIED = "jane_submitted_unverified"
R_ICBC_REJECTED_NO_RULE = "icbc_rejected_no_rule"
R_UNKNOWN_PAYER = "unknown_payer"

SCOPE_REASONS = (R_UNKNOWN_PAYER, R_UNKNOWN_STATE, R_NO_RULE_VERSION, R_UNMAPPED_CODE)


@dataclass(frozen=True)
class ClaimIn:
    id: uuid.UUID
    payer: str
    policy_status: str | None = None
    end_date: date | None = None
    treatments_count: int | None = None
    policy_max: int | None = None
    next_appointment_date: date | None = None
    date_of_event: date | None = None


@dataclass(frozen=True)
class VisitIn:
    id: uuid.UUID
    invoice_ref: str
    payer: str
    discipline: str
    date_of_service: date
    billing_code: str
    amount_invoiced: Decimal
    submission_state: str
    amount_paid: Decimal = Decimal("0.00")
    line_no: int = 1
    state_date: date | None = None
    # B1-003: a date before which the product KNOWS no rejection had happened (the export date of the
    # last snapshot in the initial run of "unsubmitted" observations). Never a guessed rejection date.
    rejected_not_before: date | None = None
    # B1-010: a date by which the first rejection had certainly happened (the first snapshot showing
    # `rejected`: its state date, or its export date). With both bounds the true PR-08 limit lies
    # between max(service + 180, not_before + 90) and max(service + 180, rejected_by + 90).
    rejected_by: date | None = None
    claim_id: uuid.UUID | None = None
    # Staff outcome on the ICBC-07 item: ICBC's portal does not have it / it was verified there.
    portal_status: PortalStatus = None


@dataclass(frozen=True)
class RuleVersionIn:
    id: uuid.UUID
    rule_code: str
    version: int
    effective_from: date
    effective_to: date | None
    params: dict[str, Any]
    source_id: str
    source_citation: str


@dataclass(frozen=True)
class Result:
    """What one rule says about one visit or claim."""

    rule_code: str
    outcome: Outcome
    reason: str | None = None
    version_id: uuid.UUID | None = None
    limit_date: date | None = None
    submit_by: date | None = None
    money_class: MoneyClass | None = None
    amount: Decimal | None = None
    near_limit: bool = False
    # B1-010: when the true limit is uncertain, `limit_date` is the earliest possible limit ("act by")
    # and `latest_limit` the latest possible one; loss is certain only after `latest_limit`.
    latest_limit: date | None = None


@dataclass(frozen=True)
class Scope:
    status: CheckStatus
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Finding:
    target: Literal["visit", "claim"]
    target_id: uuid.UUID
    result: Result


@dataclass
class Evaluation:
    on_date: date
    findings: list[Finding] = field(default_factory=list)
    scopes: dict[uuid.UUID, Scope] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        out = {"in_scope": 0, "rules_not_evaluated": 0, "could_not_check": 0, "no_rules_applied": 0}
        for s in self.scopes.values():
            out[s.status] += 1
        return out
