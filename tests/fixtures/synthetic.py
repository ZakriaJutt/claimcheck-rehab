"""Synthetic "Harbourview Physio" import rows, in the minimised shape the browser sends.

1,184 visits (ICBC 702, WorkSafeBC 311, other 171), 388 claims, service dates 12 August to
9 November 2026 (execution-plan.md "Planned tests"). Invoice references, claim tokens and every value
are generated; none comes from a real clinic. In the default ("all fine") form every ICBC and
WorkSafeBC visit is paid at the schedule fee with complete claim data, so nothing should flag;
variants plant specific conditions.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

START = date(2026, 8, 12)
END = date(2026, 11, 9)


@dataclass
class Rows:
    visits: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for v in self.visits:
            out[v["payer"]] = out.get(v["payer"], 0) + 1
        return out


def token(seed: int, n: int) -> str:
    return hashlib.sha256(f"synthetic-claim-{seed}-{n}".encode()).hexdigest()[:32]


def harbourview(seed: int = 1, unknown_states: int = 0, prefix: str = "HV") -> Rows:
    rnd = random.Random(seed)
    rows = Rows()
    inv = 0

    def add_visit(payer: str, d: date, code: str, amount: str, claim: str | None, state: str = "paid",
                  paid: str | None = None, discipline: str = "physiotherapy") -> None:
        nonlocal inv
        inv += 1
        rows.visits.append({
            "row_no": inv, "line_no": 1, "invoice_ref": f"{prefix}-{inv:06d}", "date_of_service": d.isoformat(),
            "payer": payer, "billing_code": code, "amount_invoiced": amount,
            "amount_paid": paid if paid is not None else (amount if state == "paid" else "0.00"),
            "submission_state": state, "state_date": None, "discipline": discipline, "claim_token": claim,
        })

    def add_claim(payer: str, tok: str, **kw: Any) -> None:
        rows.claims.append({"row_no": len(rows.claims) + 1, "claim_token": tok, "payer": payer,
                            "policy_status": "open", "end_date": None, "treatments_count": None,
                            "policy_max": None, "next_appointment_date": None, "date_of_event": None, **kw})

    # ICBC: 234 claims x 3 visits = 702
    for i in range(234):
        tok = token(seed, i)
        start = START + timedelta(days=i % 70)
        add_claim("ICBC", tok, end_date="2027-01-31", treatments_count=3, policy_max=25,
                  date_of_event=(start - timedelta(days=5)).isoformat())
        add_visit("ICBC", start, "ICBC-IV", "154.00", tok)
        add_visit("ICBC", start + timedelta(days=7), "ICBC-ST", "97.00", tok)
        add_visit("ICBC", start + timedelta(days=14), "ICBC-ST", "97.00", tok)
    # WorkSafeBC: 104 claims, 103 x 3 + 1 x 2 = 311
    for i in range(104):
        tok = token(seed, 1000 + i)
        start = START + timedelta(days=i % 70)
        add_claim("WSBC", tok, next_appointment_date="2026-11-20",
                  date_of_event=(start - timedelta(days=5)).isoformat())
        add_visit("WSBC", start, "19100", "196.00", tok)
        add_visit("WSBC", start + timedelta(days=6), "19102", "95.00", tok)
        if i < 103:
            add_visit("WSBC", start + timedelta(days=12), "19102", "95.00", tok)
    # Other payers: 50 claims, 171 visits, no rules applied
    for i in range(171):
        tok = token(seed, 5000 + (i % 50))
        if i < 50:
            add_claim("OTHER", tok)
        add_visit("OTHER", START + timedelta(days=rnd.randrange(0, 90)), "UNMAPPED", "80.00", tok,
                  state="unsubmitted")
    assert len(rows.visits) == 1184 and len(rows.claims) == 388
    if unknown_states:
        in_scope = [v for v in rows.visits if v["payer"] in ("ICBC", "WSBC")]
        for v in rnd.sample(in_scope, unknown_states):
            v["submission_state"] = "unknown"  # Jane wording the profile does not recognise
    return rows
