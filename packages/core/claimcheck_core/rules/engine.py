"""Scope check, then every applicable rule independently (T-4.1.1; MH-03; HCF-1).

Invariants enforced here, centrally, whatever a rule returns:
- Only an in-scope visit (or a claim with an in-scope visit) can produce `clear`. Any `clear` on a
  visit that could not be checked becomes `not_evaluated(<scope reason>)`.
- A date with no loaded version for a rule gives `not_evaluated(no_rule_version)` for that rule.
- `not_evaluated` never stops another rule: each rule runs in its own call.
- Visits with no rules applied get no findings but are counted.
- Same input and versions give the same output in any input order (UT-09).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import replace
from datetime import date

from claimcheck_core.dates import in_range
from claimcheck_core.rules.payer_rules import CLAIM_RULES, DEADLINE_RULES, VISIT_RULES, Context
from claimcheck_core.rules.types import (
    ICBC,
    ICBC_KNOWN_CODES,
    OTHER,
    R_NO_CLAIM_LINK,
    R_NO_RULE_VERSION,
    R_UNKNOWN_PAYER,
    R_UNKNOWN_STATE,
    R_UNMAPPED_CODE,
    UNKNOWN_PAYER,
    UNMAPPED,
    WSBC,
    ClaimIn,
    Evaluation,
    Finding,
    Result,
    RuleVersionIn,
    Scope,
    VisitIn,
)


class VersionIndex:
    def __init__(self, versions: list[RuleVersionIn]) -> None:
        self._by_code: dict[str, list[RuleVersionIn]] = defaultdict(list)
        for v in versions:
            self._by_code[v.rule_code].append(v)
        for vs in self._by_code.values():
            vs.sort(key=lambda x: (x.effective_from, x.version))

    def for_date(self, rule_code: str, on: date) -> RuleVersionIn | None:
        found = [v for v in self._by_code.get(rule_code, []) if in_range(on, v.effective_from, v.effective_to)]
        if len(found) > 1:  # the database exclusion constraint forbids this; refuse to guess
            raise ValueError(f"overlapping published versions for {rule_code}")
        return found[0] if found else None


def scope_of(v: VisitIn, idx: VersionIndex) -> Scope:
    if v.payer == UNKNOWN_PAYER or v.payer not in (ICBC, WSBC, OTHER):
        # Jane's payer wording was not recognised: it may be ICBC or WorkSafeBC (B1-007).
        return Scope("could_not_check", (R_UNKNOWN_PAYER,))
    if v.payer == OTHER:
        return Scope("no_rules_applied", ("other_payer",))
    if v.payer == ICBC and v.discipline != "physiotherapy":
        return Scope("no_rules_applied", ("discipline_out_of_scope",))
    reasons: list[str] = []
    if v.submission_state == "unknown":
        reasons.append(R_UNKNOWN_STATE)
    if v.payer == ICBC:
        fee_version = idx.for_date("ICBC-06", v.date_of_service)
        if v.billing_code == UNMAPPED or v.billing_code not in ICBC_KNOWN_CODES:
            reasons.append(R_UNMAPPED_CODE)
        elif fee_version is None or v.billing_code not in fee_version.params["fees"]:
            # e.g. Hand Therapy before 2026-09-27: the service did not exist in the loaded schedule
            # for that date (Decision.md 4.1: "outside that period: could not check"; B1-002).
            reasons.append(R_NO_RULE_VERSION)
    else:
        fee_version = idx.for_date("WSBC-08", v.date_of_service)
        if fee_version is None:
            reasons.append(R_NO_RULE_VERSION)  # PR-11 defines what is in scope; no table, no check
        elif v.billing_code == UNMAPPED or v.billing_code not in fee_version.params["fees"]:
            reasons.append(R_UNMAPPED_CODE)
    if reasons:
        return Scope("could_not_check", tuple(reasons))
    return Scope("in_scope")


def _enforce_scope(res: Result, scope: Scope) -> Result:
    if scope.status != "in_scope" and res.outcome == "clear":
        return replace(res, outcome="not_evaluated", reason=scope.reasons[0])
    return res


def evaluate(
    visits: list[VisitIn], claims: list[ClaimIn], versions: list[RuleVersionIn], on_date: date
) -> Evaluation:
    idx = VersionIndex(versions)
    ordered = sorted(visits, key=lambda v: (v.date_of_service, v.invoice_ref, v.line_no, str(v.id)))
    claim_map = {c.id: c for c in claims}
    by_claim: dict[uuid.UUID, list[VisitIn]] = defaultdict(list)
    for v in ordered:
        if v.claim_id is not None:
            by_claim[v.claim_id].append(v)
    ctx = Context(on_date=on_date, claims=claim_map, visits_by_claim=dict(by_claim))
    out = Evaluation(on_date=on_date)

    for v in ordered:
        scope = scope_of(v, idx)
        out.scopes[v.id] = scope
        if scope.status == "no_rules_applied" or v.payer not in VISIT_RULES:
            continue  # counted; an unknown payer has no rule set to attempt
        for code, fn in sorted(VISIT_RULES[v.payer].items()):
            ver = idx.for_date(code, v.date_of_service)
            if ver is None:
                res = Result(code, "not_evaluated", R_NO_RULE_VERSION)
            elif scope.status == "could_not_check" and code in DEADLINE_RULES:
                res = Result(code, "not_evaluated", scope.reasons[0], ver.id)
            else:
                res = fn(v, ver, ctx)
            out.findings.append(Finding("visit", v.id, _enforce_scope(res, scope)))
        if v.claim_id is None or v.claim_id not in claim_map:
            # Claim-level rules cannot run without a claim link; say so on the visit (M-08).
            for code in sorted(CLAIM_RULES[v.payer]):
                ver = idx.for_date(code, v.date_of_service)
                reason = R_NO_CLAIM_LINK if ver else R_NO_RULE_VERSION
                out.findings.append(Finding("visit", v.id, Result(code, "not_evaluated", reason,
                                                                  ver.id if ver else None)))

    claim_findings: dict[uuid.UUID, list[Result]] = defaultdict(list)
    for claim_id in sorted(by_claim, key=str):
        claim = claim_map.get(claim_id)
        if claim is None or claim.payer not in CLAIM_RULES:
            continue
        relevant = [v for v in by_claim[claim_id]
                    if v.payer == claim.payer and out.scopes[v.id].status != "no_rules_applied"]
        if not relevant:
            continue
        in_scope = [v for v in relevant if out.scopes[v.id].status == "in_scope"]
        claim_scope = Scope("in_scope") if in_scope else out.scopes[relevant[0].id]
        version_date = max(v.date_of_service for v in (in_scope or relevant))
        for code, cfn in sorted(CLAIM_RULES[claim.payer].items()):
            ver = idx.for_date(code, version_date)
            if ver is None:
                res = Result(code, "not_evaluated", R_NO_RULE_VERSION)
            else:
                res = cfn(claim, relevant, ver, ctx)
            res = _enforce_scope(res, claim_scope)
            claim_findings[claim_id].append(res)
            out.findings.append(Finding("claim", claim_id, res))

    # B1-002: an in-scope visit with any applicable rule not evaluated (its own or its claim's) is
    # never "checked": it gets its own status and a list row naming the rule and the reason.
    visit_findings: dict[uuid.UUID, list[Result]] = defaultdict(list)
    for f in out.findings:
        if f.target == "visit":
            visit_findings[f.target_id].append(f.result)
    for v in ordered:
        if out.scopes[v.id].status != "in_scope":
            continue
        results = visit_findings[v.id] + (claim_findings.get(v.claim_id, []) if v.claim_id else [])
        missing = sorted({f"{r.rule_code}:{r.reason}" for r in results if r.outcome == "not_evaluated"})
        if missing:
            out.scopes[v.id] = Scope("rules_not_evaluated", tuple(missing))
    return out
