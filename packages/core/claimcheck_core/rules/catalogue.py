"""Rule-version catalogue for B1 (T-1.1.1 parameters, T-4.1.5 publication).

Every rule type, not only fees, carries an effective date range applied to the date of service
(Decision.md section 4.1, "Effective dates of every rule"). Outside every range the result is
`not_evaluated(no_rule_version)`, never `clear`.

Figures are transcribed from the PR rows of Decision.md section 4.1, which record the payer documents
SRC-12, SRC-13, SRC-19 and SRC-20 as opened on 2026-11-10. They were NOT re-read against the payer PDFs
during B1; T-4.1.5 re-reads them before any version is published to a clinic.

C1 (2026-11-11): the WorkSafeBC Physiotherapy Services Reference Manual page is now dated June 2026 and
says the manual is used with the Physiotherapy Services Memorandum of Agreement and its schedules,
effective 2026-04-01 (SRC-19, re-opened 2026-11-11; the downloaded PDF was created 2026-06-26 and its
footer still reads "February 2026"). PR-07, PR-08, PR-09 and PR-12 read the same, on the same pages
(27, 29-30, 38). The rules citing SRC-19 get version 2 with the new citation and unchanged parameters;
version 1 of each is marked `superseded` when version 2 is published (`SUPERSEDED`).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from typing import Any

from claimcheck_core.rules.types import (
    ICBC_HAND_15,
    ICBC_HAND_30,
    ICBC_HAND_45,
    ICBC_INITIAL,
    ICBC_SPECIALIZED,
    ICBC_STANDARD,
    RuleVersionIn,
)

D = date.fromisoformat
_NS = uuid.UUID("6f1b4c1e-5d0a-4b8e-9a51-0c1a2b3c4d5e")

ICBC_BASE_FEES = {ICBC_INITIAL: "154.00", ICBC_STANDARD: "97.00", ICBC_SPECIALIZED: "145.00"}
ICBC_HAND_FEES = {ICBC_HAND_15: "97.00", ICBC_HAND_30: "110.00", ICBC_HAND_45: "145.00"}

WSBC_FEES = {
    "19100": "196.00", "19101": "196.00", "19102": "95.00", "19103": "57.00", "19303": "57.00",
    "19105": "45.00", "19204": "33.25", "19106": "95.00", "19107": "70.00", "19108": "65.00",
    "19109": "115.00", "19171": "42.00", "19193": "67.00", "19313": "48.00",
}

M26 = "manual June 2026 ed., with the MOA and schedules effective 2026-04-01"

# (rule_code, version, from, to, params, source_id, citation)
_CATALOGUE: list[tuple[str, int, date, date | None, dict[str, Any], str, str]] = [
    ("ICBC-01", 1, D("2026-04-01"), None,
     {"limit_days": 45, "flag_after_days": 14, "near_limit_from_day": 31}, "SRC-12", "PR-01; guide s. 6.1"),
    ("ICBC-02", 1, D("2026-04-01"), None,
     {"pre_authorized": 25, "warn_at": 22}, "SRC-12", "PR-02; guide ss. 1, 4.3"),
    ("ICBC-03", 1, D("2026-04-01"), None,
     {"early_access_days": 84}, "SRC-12", "PR-02, PR-03; guide ss. 1, 4.3, 5"),
    ("ICBC-04", 1, D("2026-04-01"), None, {}, "SRC-12", "PR-04; guide ss. 4.2, 4.3"),
    ("ICBC-05", 1, D("2026-04-01"), None, {}, "SRC-12", "PR-04; guide s. 4.12"),
    ("ICBC-06", 1, D("2026-04-01"), D("2026-09-26"),
     {"fees": dict(ICBC_BASE_FEES)}, "SRC-13", "PR-05; fee schedule CL534, column from 2026-04-01"),
    ("ICBC-06", 2, D("2026-09-27"), None,
     {"fees": {**ICBC_BASE_FEES, **ICBC_HAND_FEES}}, "SRC-13",
     "PR-05; fee schedule CL534, columns from 2026-04-01 and Hand Therapy from 2026-09-27"),
    ("ICBC-07", 1, D("2026-04-01"), None,
     {"limit_days": 45, "flag_after_days": 14, "chase_after_days": 30}, "SRC-12", "Gap G-4; PR-01"),
    ("ICBC-08", 1, D("2026-04-01"), None, {}, "SRC-12", "Gap G-3; PR-02"),
    ("WSBC-01", 2, D("2026-04-01"), None,
     {"limit_days": 90, "flag_after_days": 14, "near_limit_from_day": 76}, "SRC-19",
     f"PR-07; {M26}, p. 27"),
    ("WSBC-02", 2, D("2026-04-01"), None,
     {"service_limit_days": 180, "rejection_limit_days": 90, "near_limit_days": 14}, "SRC-19",
     f"PR-08; {M26}, pp. 27, 30"),
    ("WSBC-03", 2, D("2026-04-01"), None, {}, "SRC-19", f"PR-12; {M26}, pp. 28-29"),
    ("WSBC-04", 2, D("2026-04-01"), None,
     {"treatment_codes": ["19102", "19107", "19108"]}, "SRC-19", f"PR-09; {M26}, pp. 38-39"),
    ("WSBC-05", 1, D("2026-04-01"), None,
     {"follow_up": "19102", "initial_codes": ["19100", "19101"]}, "SRC-20", "PR-10"),
    ("WSBC-06", 1, D("2026-04-01"), None,
     {"initial_code": "19100", "within_days": 60}, "SRC-20", "PR-10"),
    ("WSBC-07", 2, D("2026-04-01"), None,
     {"treatment_codes": ["19102", "19107", "19108"], "max_visits": 10, "max_days": 35}, "SRC-19",
     f"PR-09; {M26}, pp. 38-39, 41"),
    ("WSBC-08", 1, D("2026-04-01"), D("2027-03-31"),
     {"fees": dict(WSBC_FEES)}, "SRC-20", "PR-11; fee schedule column 2026-04-01 to 2027-03-31"),
    ("WSBC-09", 1, D("2026-04-01"), D("2027-03-31"),
     {"report_code": "19105", "report_fee": "45.00", "idle_days": 14}, "SRC-20", "PR-11"),
    ("WSBC-10", 2, D("2026-04-01"), None, {"unpaid_days": 30}, "SRC-19", f"Gap G-4; {M26}"),
]


# Versions replaced in C1 by version 2 over the same dates; publication marks them `superseded` first, so
# the no-overlap constraint on published versions holds.
SUPERSEDED: frozenset[tuple[str, int]] = frozenset(
    {("WSBC-01", 1), ("WSBC-02", 1), ("WSBC-03", 1), ("WSBC-04", 1), ("WSBC-07", 1), ("WSBC-10", 1)})


def catalogue_versions() -> list[RuleVersionIn]:
    out = []
    for code, ver, start, end, params, src, cite in _CATALOGUE:
        vid = uuid.uuid5(_NS, f"{code}:{ver}")
        out.append(RuleVersionIn(vid, code, ver, start, end, params, src, cite))
    return out


ALL_RULE_CODES = tuple(sorted({row[0] for row in _CATALOGUE}))


def rule_set_hash(versions: list[RuleVersionIn]) -> str:
    """Stable hash of the loaded versions; part of the evaluation idempotency key."""
    blob = json.dumps(
        sorted(
            [v.rule_code, v.version, v.effective_from.isoformat(),
             v.effective_to.isoformat() if v.effective_to else None, v.params]
            for v in versions
        ),
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
