"""Synthetic builders for rule tests. No real clinic data: invoice refs are made up (S-nnnn)."""

from __future__ import annotations

import itertools
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from claimcheck_core.rules.catalogue import catalogue_versions
from claimcheck_core.rules.engine import evaluate
from claimcheck_core.rules.types import ClaimIn, Evaluation, Result, VisitIn

D = date.fromisoformat
_counter = itertools.count(1)
VERSIONS = catalogue_versions()


def visit(**kw: Any) -> VisitIn:
    n = next(_counter)
    base: dict[str, Any] = {
        "id": uuid.uuid4(), "invoice_ref": f"S-{n:05d}", "payer": "ICBC", "discipline": "physiotherapy",
        "date_of_service": D("2026-10-01"), "billing_code": "ICBC-ST", "amount_invoiced": Decimal("97.00"),
        "submission_state": "unsubmitted",
    }
    base.update(kw)
    if isinstance(base["date_of_service"], str):
        base["date_of_service"] = D(base["date_of_service"])
    for k in ("amount_invoiced", "amount_paid"):
        if k in base and not isinstance(base[k], Decimal):
            base[k] = Decimal(str(base[k]))
    return VisitIn(**base)


def claim(**kw: Any) -> ClaimIn:
    base: dict[str, Any] = {"id": uuid.uuid4(), "payer": "ICBC"}
    base.update(kw)
    return ClaimIn(**base)


def run(visits: list[VisitIn], claims: list[ClaimIn] | None = None, on: str | date = "2026-10-15") -> Evaluation:
    on_d = D(on) if isinstance(on, str) else on
    return evaluate(visits, claims or [], VERSIONS, on_d)


def result(ev: Evaluation, target_id: uuid.UUID, rule: str) -> Result:
    found = [f.result for f in ev.findings if f.target_id == target_id and f.result.rule_code == rule]
    assert len(found) == 1, f"expected one {rule} finding, got {len(found)}"
    return found[0]


def outcomes(ev: Evaluation, target_id: uuid.UUID) -> dict[str, str]:
    return {f.result.rule_code: f.result.outcome for f in ev.findings if f.target_id == target_id}
