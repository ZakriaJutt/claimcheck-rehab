"""The import payload contract: 16 allow-listed fields plus two ordinals (schema.md section 2).

Any other key, a value of the wrong type or pattern, or an enumeration outside its closed list rejects
the whole request. Error details name the row number, field and a code; they never echo a value.
A required field that is null (the browser could not read it) does not reject the request: the row
is staged and counted as rejected with a reason from a fixed list at finalize (IT-03).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

VISIT_FIELDS = (
    "invoice_ref", "date_of_service", "payer", "billing_code", "amount_invoiced", "amount_paid",
    "submission_state", "state_date", "discipline", "claim_token",
)
CLAIM_FIELDS = (
    "claim_token", "payer", "policy_status", "end_date", "treatments_count", "policy_max",
    "next_appointment_date", "date_of_event",
)
ALLOWED_FIELDS = frozenset(VISIT_FIELDS) | frozenset(CLAIM_FIELDS)  # exactly 16
ORDINALS = ("row_no", "line_no")
VISIT_KEYS = frozenset(VISIT_FIELDS) | {"row_no", "line_no"}
CLAIM_KEYS = frozenset(CLAIM_FIELDS) | {"row_no"}
assert len(ALLOWED_FIELDS) == 16

PAYERS = frozenset({"ICBC", "WSBC", "OTHER"})
STATES = frozenset({"unsubmitted", "submitted", "rejected", "partly_paid", "paid", "unknown"})
DISCIPLINES = frozenset({"physiotherapy", "support", "other"})
POLICY_STATUSES = frozenset({"open", "closed", "other"})

# Interim pattern until T-0.1.2 records Jane's invoice-number format (TRD: "too loose to rely on").
INVOICE_REF_RE = re.compile(r"^[A-Za-z0-9-]{1,20}$")
TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
AMOUNT_RE = re.compile(r"^\d{1,4}(\.\d{1,2})?$")
CODE_RE = re.compile(r"^[A-Za-z0-9-]{1,12}$")
MAX_AMOUNT = Decimal("2000")

VISIT_REQUIRED = ("invoice_ref", "date_of_service", "payer", "billing_code", "amount_invoiced",
                  "submission_state", "discipline")
CLAIM_REQUIRED = ("claim_token", "payer")
REJECT_REASONS = frozenset({"missing_required", "duplicate_row"})


@dataclass(frozen=True)
class FieldError:
    row_no: int | None
    field: str
    code: str


class ContractError(Exception):
    def __init__(self, errors: list[FieldError]) -> None:
        super().__init__("contract")
        self.errors = errors


def _date(v: Any) -> date:
    if not isinstance(v, str) or not DATE_RE.match(v):
        raise ValueError
    return date.fromisoformat(v)


def _amount(v: Any) -> Decimal:
    if not isinstance(v, str) or not AMOUNT_RE.match(v):
        raise ValueError
    try:
        d = Decimal(v)
    except InvalidOperation as exc:  # pragma: no cover - regex already guards
        raise ValueError from exc
    if d > MAX_AMOUNT:
        raise ValueError
    return d


def _int(v: Any, lo: int, hi: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise ValueError
    return v


def _enum(allowed: frozenset[str]) -> Any:
    def check(v: Any) -> str:
        if not isinstance(v, str) or v not in allowed:
            raise ValueError
        return v
    return check


def _pattern(rx: re.Pattern[str]) -> Any:
    def check(v: Any) -> str:
        if not isinstance(v, str) or not rx.match(v):
            raise ValueError
        return v
    return check


FIELD_PARSERS: dict[str, Any] = {
    "invoice_ref": _pattern(INVOICE_REF_RE),
    "date_of_service": _date, "state_date": _date, "end_date": _date,
    "next_appointment_date": _date, "date_of_event": _date,
    "payer": _enum(PAYERS), "submission_state": _enum(STATES), "discipline": _enum(DISCIPLINES),
    "policy_status": _enum(POLICY_STATUSES),
    "billing_code": _pattern(CODE_RE), "claim_token": _pattern(TOKEN_RE),
    "amount_invoiced": _amount, "amount_paid": _amount,
    "treatments_count": lambda v: _int(v, 0, 1000), "policy_max": lambda v: _int(v, 0, 1000),
}


def parse_rows(kind: str, rows: Any, allowed_codes: frozenset[str]) -> list[dict[str, Any]]:
    """Validate one request's rows of one kind. Raises ContractError naming fields, never values."""
    if not isinstance(rows, list):
        raise ContractError([FieldError(None, kind, "not_a_list")])
    keys = VISIT_KEYS if kind == "visit" else CLAIM_KEYS
    errors: list[FieldError] = []
    out: list[dict[str, Any]] = []
    seen_row_nos: set[int] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            errors.append(FieldError(None, kind, "not_an_object"))
            continue
        row_no = raw.get("row_no")
        rn = row_no if isinstance(row_no, int) and not isinstance(row_no, bool) and row_no > 0 else None
        if rn is None:
            errors.append(FieldError(None, "row_no", "invalid"))
        elif rn in seen_row_nos:
            errors.append(FieldError(rn, "row_no", "repeated_in_request"))
        else:
            seen_row_nos.add(rn)
        for key in raw:
            if key not in keys:
                # Only the key name is reported; an unknown key may itself be an identifier column.
                errors.append(FieldError(rn, "unknown_field", "not_allowed"))
        parsed: dict[str, Any] = {"row_no": rn}
        if kind == "visit":
            try:
                parsed["line_no"] = _int(raw.get("line_no", 1), 1, 999)
            except ValueError:
                errors.append(FieldError(rn, "line_no", "invalid"))
        for f in (VISIT_FIELDS if kind == "visit" else CLAIM_FIELDS):
            v = raw.get(f)
            if v is None:
                parsed[f] = None
                continue
            try:
                parsed[f] = FIELD_PARSERS[f](v)
            except ValueError:
                errors.append(FieldError(rn, f, "invalid"))
        code = parsed.get("billing_code")
        if kind == "visit" and code is not None and code != "UNMAPPED" and code not in allowed_codes:
            errors.append(FieldError(rn, "billing_code", "not_in_profile"))
        out.append(parsed)
    if errors:
        raise ContractError(errors)
    return out


def missing_required(kind: str, row: dict[str, Any]) -> bool:
    req = VISIT_REQUIRED if kind == "visit" else CLAIM_REQUIRED
    return any(row.get(f) is None for f in req)


def to_json(row: dict[str, Any]) -> dict[str, Any]:
    """Staging representation (import_row.payload): ISO dates, decimal strings."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, date):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = str(v)
        else:
            out[k] = v
    return out


def from_json(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    for f in ("date_of_service", "state_date", "end_date", "next_appointment_date", "date_of_event"):
        if out.get(f) is not None:
            out[f] = date.fromisoformat(out[f])
    for f in ("amount_invoiced", "amount_paid"):
        if out.get(f) is not None:
            out[f] = Decimal(out[f])
    return out
