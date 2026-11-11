"""evaluate_clinic job: load, run the engine, persist findings and items, check for escapes (M-09)
and the could-not-check share (T-4.1.1, T-4.1.4; MH-03, MH-04; HCF-1)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from claimcheck_core.alerts import Alerter, default_alerter
from claimcheck_core.audit import write_audit
from claimcheck_core.dates import add_days, local_date_of
from claimcheck_core.items import ItemState, next_item
from claimcheck_core.logging import get_correlation_id, get_logger, log_event
from claimcheck_core.models import (
    Claim,
    EvaluationRun,
    Finding,
    ImportBatch,
    Item,
    ItemEvent,
    RuleVersion,
    Visit,
    VisitSnapshot,
)
from claimcheck_core.rules.catalogue import rule_set_hash
from claimcheck_core.rules.engine import evaluate
from claimcheck_core.rules.types import ClaimIn, Evaluation, Result, RuleVersionIn, VisitIn
from claimcheck_core.tenancy import tenant_session

_log = get_logger("evaluation")

DEADLINE_LOSS_RULES = ("ICBC-01", "WSBC-01", "WSBC-02")
COVERING_RULES = frozenset({"ICBC-01", "ICBC-07", "WSBC-01", "WSBC-02", "WSBC-10"})
ESCAPE_NOTICE_DAYS = 7
PORTAL_OUTCOMES = {"portal_not_received": "not_received", "verified_in_portal": "verified",
                   "payer_declined": "payer_declined"}
# C1: a visit that passed a deadline is an escape whether the payer's rule makes the loss certain or leaves
# payment at its discretion; M-09 counts both (HCF-1), it does not call either a confirmed loss.
PAST_DEADLINE_CLASSES = frozenset({"permanent_certain", "past_deadline_discretionary"})
COULD_NOT_CHECK_ALERT_SHARE = 0.05


@dataclass
class EvaluationSummary:
    run_id: uuid.UUID
    counts: dict[str, int]
    flags: int
    not_evaluated: int
    escapes: list[uuid.UUID] = field(default_factory=list)


def load_published_versions(s: Session) -> list[RuleVersionIn]:
    rows = s.scalars(select(RuleVersion).where(RuleVersion.status == "published"))
    return [RuleVersionIn(r.id, r.rule_code, r.version, r.effective_from, r.effective_to, r.params,
                          r.source_id, r.source_citation) for r in rows]


def _portal_and_outcomes(s: Session) -> tuple[dict[uuid.UUID, str | None], dict[uuid.UUID, date]]:
    """Portal status per visit (from staff outcomes on its ICBC items) and the local date of the latest
    outcome per item. An 'undone' event cancels the outcome before it."""
    portal: dict[uuid.UUID, str | None] = {}
    last_outcome: dict[uuid.UUID, date] = {}
    q = (select(ItemEvent.item_id, ItemEvent.kind, ItemEvent.outcome, ItemEvent.created_at, Item.visit_id)
         .join(Item, Item.id == ItemEvent.item_id)
         .where(ItemEvent.kind.in_(("outcome", "undone"))).order_by(ItemEvent.created_at, ItemEvent.id))
    for item_id, kind, outcome, created_at, visit_id in s.execute(q):
        if kind == "outcome":
            last_outcome[item_id] = local_date_of(created_at)
            if visit_id and outcome in PORTAL_OUTCOMES:
                portal[visit_id] = PORTAL_OUTCOMES[outcome]
        else:
            last_outcome.pop(item_id, None)
            if visit_id:
                portal[visit_id] = None
    return portal, last_outcome


def rejection_lower_bounds(s: Session) -> dict[uuid.UUID, date]:
    """B1-003: per visit, the export date of the last snapshot in the initial run of 'unsubmitted'
    observations. Before that date the invoice had never been submitted, so it had never been rejected.
    A visit first seen in any other state has no bound (WSBC-02 then uses service + 180)."""
    out: dict[uuid.UUID, date] = {}
    broken: set[uuid.UUID] = set()
    q = select(VisitSnapshot.visit_id, VisitSnapshot.export_date, VisitSnapshot.submission_state).order_by(
        VisitSnapshot.visit_id, VisitSnapshot.export_date, VisitSnapshot.created_at)
    for vid, export_date, state in s.execute(q):
        if vid in broken:
            continue
        if state == "unsubmitted":
            out[vid] = export_date
        else:
            broken.add(vid)
    return out


def rejection_upper_bounds(s: Session) -> dict[uuid.UUID, date]:
    """B1-010: per visit, a date by which the first rejection had certainly happened: the first snapshot
    (by export date) showing `rejected`, using its state date when Jane exported one (the rejection then
    current, which is no earlier than the first), else its export date."""
    out: dict[uuid.UUID, date] = {}
    q = select(VisitSnapshot.visit_id, VisitSnapshot.export_date, VisitSnapshot.state_date).where(
        VisitSnapshot.submission_state == "rejected").order_by(
        VisitSnapshot.visit_id, VisitSnapshot.export_date, VisitSnapshot.created_at)
    for vid, export_date, state_date in s.execute(q):
        if vid not in out:
            out[vid] = min(export_date, state_date) if state_date else export_date
    return out


def _visit_in(v: Visit, portal: str | None, not_before: date | None = None,
              rejected_by: date | None = None) -> VisitIn:
    return VisitIn(id=v.id, invoice_ref=v.invoice_ref, payer=v.payer, discipline=v.discipline,
                   date_of_service=v.date_of_service, billing_code=v.billing_code,
                   amount_invoiced=v.amount_invoiced, amount_paid=v.amount_paid,
                   submission_state=v.submission_state, line_no=v.line_no, state_date=v.state_date,
                   rejected_not_before=not_before, rejected_by=rejected_by, claim_id=v.claim_id,
                   portal_status=portal)  # type: ignore[arg-type]


def _claim_in(c: Claim) -> ClaimIn:
    return ClaimIn(id=c.id, payer=c.payer, policy_status=c.policy_status, end_date=c.end_date,
                   treatments_count=c.treatments_count, policy_max=c.policy_max,
                   next_appointment_date=c.next_appointment_date, date_of_event=c.date_of_event)


def _state(i: Item) -> ItemState:
    return ItemState(i.rule_code, i.status, i.money_class, i.amount, i.limit_date,  # type: ignore[arg-type]
                     i.first_flagged_on, i.class_at_first_flag, i.reached_near_limit_on, i.version)  # type: ignore[arg-type]


def find_escapes(
    ev: Evaluation,
    visits: dict[uuid.UUID, Visit],
    items_before: dict[tuple[str, uuid.UUID, str], ItemState],
    status_before: dict[uuid.UUID, str | None],
) -> list[uuid.UUID]:
    """M-09: visits now past a deadline rule's limit (certain or at the payer's discretion), present in an
    import at least 7 days before the limit, with no item flagged by the limit and no 'could not check' entry."""
    out: set[uuid.UUID] = set()
    for f in ev.findings:
        r = f.result
        if (f.target != "visit" or r.rule_code not in DEADLINE_LOSS_RULES or r.outcome != "flag"
                or r.money_class not in PAST_DEADLINE_CLASSES or r.limit_date is None):
            continue
        v = visits[f.target_id]
        if v.first_seen_export_date > add_days(r.limit_date, -ESCAPE_NOTICE_DAYS):
            continue  # not present early enough to have been caught
        if status_before.get(v.id) in ("could_not_check", "rules_not_evaluated"):
            continue  # it was listed as not checked
        covered = any(
            (st := items_before.get(("visit", v.id, rule))) is not None and st.first_flagged_on <= r.limit_date
            for rule in COVERING_RULES)
        if not covered:
            out.add(v.id)
    return sorted(out, key=str)


def evaluate_clinic(
    engine: Engine, clinic_id: uuid.UUID, on_date: date, trigger: str = "daily",
    alerter: Alerter = default_alerter,
) -> EvaluationSummary:
    corr = uuid.UUID(get_correlation_id() or str(uuid.uuid4()))
    with tenant_session(engine, clinic_id) as s:
        versions = load_published_versions(s)
        rhash = rule_set_hash(versions)
        run_stmt = insert(EvaluationRun).values(clinic_id=clinic_id, local_date=on_date, rule_set_hash=rhash,
                                                trigger=trigger, status="running", correlation_id=corr)
        upsert = run_stmt.on_conflict_do_update(
            constraint="evaluation_run_unique_key",
            set_={"status": "running", "correlation_id": corr, "finished_at": None})
        run_id = s.execute(upsert.returning(EvaluationRun.id)).scalar_one()

        visits = {v.id: v for v in s.scalars(select(Visit))}
        claims = list(s.scalars(select(Claim)))
        portal, last_outcome = _portal_and_outcomes(s)
        bounds = rejection_lower_bounds(s)
        uppers = rejection_upper_bounds(s)
        vin = [_visit_in(v, portal.get(v.id), bounds.get(v.id),
                         uppers.get(v.id) or (v.last_export_date if v.submission_state == "rejected" else None))
               for v in visits.values()]
        ev = evaluate(vin, [_claim_in(c) for c in claims], versions, on_date)

        items: dict[tuple[str, uuid.UUID, str], Item] = {}
        for i in s.scalars(select(Item)):
            tid = i.visit_id or i.claim_id
            assert tid is not None
            items[("visit" if i.visit_id else "claim", tid, i.rule_code)] = i
        items_before = {k: _state(i) for k, i in items.items()}
        status_before = {vid: v.check_status for vid, v in visits.items()}
        escapes = find_escapes(ev, visits, items_before, status_before)

        _persist_findings(s, clinic_id, run_id, on_date, ev)
        for vid, scope in ev.scopes.items():
            v = visits[vid]
            reason = ",".join(scope.reasons) if scope.reasons else None
            if (v.check_status, v.check_reason) != (scope.status, reason):
                v.check_status, v.check_reason = scope.status, reason

        claim_export: dict[uuid.UUID, date] = defaultdict(lambda: date.min)
        for v in visits.values():
            if v.claim_id:
                claim_export[v.claim_id] = max(claim_export[v.claim_id], v.last_export_date)
        vin_by_id = {v.id: v for v in vin}
        results: dict[tuple[str, uuid.UUID, str], Result] = {
            (f.target, f.target_id, f.result.rule_code): f.result for f in ev.findings}
        for key in sorted(set(results) | set(items), key=lambda k: (k[0], str(k[1]), k[2])):
            res = results.get(key)
            if res is None:
                continue  # rule no longer applies to this target: leave the item and its history
            item = items.get(key)
            if item is None and res.outcome != "flag":
                continue
            target, tid, _ = key
            export_date = visits[tid].last_export_date if target == "visit" else claim_export[tid]
            outcome_on = last_outcome.get(item.id) if item else None
            newer = outcome_on is not None and export_date > outcome_on
            new, events = next_item(_state(item) if item else None, res, on_date,
                                    vin_by_id.get(tid) if target == "visit" else None, newer,
                                    had_outcome=outcome_on is not None)
            _apply_item(s, clinic_id, target, tid, item, new, events, res, run_id)

        flags = sum(1 for f in ev.findings if f.result.outcome == "flag")
        ne = sum(1 for f in ev.findings if f.result.outcome == "not_evaluated")
        counts = ev.counts()
        checked_population = counts["in_scope"] + counts["could_not_check"]
        checked_population += counts["rules_not_evaluated"]
        if checked_population and counts["could_not_check"] / checked_population > COULD_NOT_CHECK_ALERT_SHARE:
            alerter.alert(s, "could_not_check_share", clinic_id, could_not_check=counts["could_not_check"],
                          in_scope=counts["in_scope"])
        for vid in escapes:
            write_audit(s, "m09_escape", "detected", clinic_id, None, "visit", vid)
            alerter.alert(s, "m09_escape", clinic_id, escapes=len(escapes))
        s.execute(update(EvaluationRun).where(EvaluationRun.id == run_id)
                  .values(status="succeeded", finished_at=datetime.now(tz=UTC)))
        write_audit(s, "evaluation_run", "succeeded", clinic_id, None, "evaluation_run", run_id,
                    {**counts, "flags": flags, "not_evaluated": ne, "escapes": len(escapes)})
        log_event(_log, "evaluation_done", clinic_id=str(clinic_id), flags=flags, not_evaluated=ne, **counts)
        return EvaluationSummary(run_id, counts, flags, ne, escapes)


def _persist_findings(s: Session, clinic_id: uuid.UUID, run_id: uuid.UUID, on_date: date, ev: Evaluation) -> None:
    rows: dict[str, list[dict[str, Any]]] = {"visit": [], "claim": []}
    for f in ev.findings:
        r = f.result
        rows[f.target].append({
            "clinic_id": clinic_id, "visit_id": f.target_id if f.target == "visit" else None,
            "claim_id": f.target_id if f.target == "claim" else None, "rule_code": r.rule_code,
            "rule_version_id": r.version_id, "outcome": r.outcome, "reason_code": r.reason,
            "limit_date": r.limit_date, "submit_by": r.submit_by, "latest_limit_date": r.latest_limit,
            "evaluation_run_id": run_id,
            "evaluated_on": on_date,
        })
    for target, batch in rows.items():
        col = "visit_id" if target == "visit" else "claim_id"
        for i in range(0, len(batch), 1000):
            stmt = insert(Finding).values(batch[i:i + 1000])
            s.execute(stmt.on_conflict_do_update(
                index_elements=[col, "rule_code"], index_where=Finding.__table__.c[col].isnot(None),
                set_={k: stmt.excluded[k] for k in ("rule_version_id", "outcome", "reason_code", "limit_date",
                                                    "submit_by", "latest_limit_date", "evaluation_run_id",
                                                    "evaluated_on")}))


def _apply_item(
    s: Session, clinic_id: uuid.UUID, target: str, tid: uuid.UUID, item: Item | None, new: ItemState | None,
    events: list[str], res: Result, run_id: uuid.UUID,
) -> None:
    if new is None:
        return
    if item is None:
        item = Item(clinic_id=clinic_id, visit_id=tid if target == "visit" else None,
                    claim_id=tid if target == "claim" else None, rule_code=new.rule_code,
                    money_class=new.money_class, amount=new.amount, limit_date=new.limit_date,
                    status=new.status, first_flagged_on=new.first_flagged_on,
                    class_at_first_flag=new.class_at_first_flag,
                    reached_near_limit_on=new.reached_near_limit_on, version=new.version)
        s.add(item)
        s.flush()
    elif new != _state(item):
        item.status, item.money_class, item.amount = new.status, new.money_class, new.amount
        item.limit_date, item.version = new.limit_date, new.version
        if item.reached_near_limit_on is None and new.reached_near_limit_on is not None:
            item.reached_near_limit_on = new.reached_near_limit_on
    for kind in events:
        s.add(ItemEvent(clinic_id=clinic_id, item_id=item.id, kind=kind,
                        idempotency_key=f"system:{run_id}:{kind}:{item.version}"))


# ------------------------------------------------------------------ freshness (MH-04 b; IT-16)

IMPORT_STALE_DAYS = 8
EVALUATION_STALE = timedelta(hours=36)


@dataclass(frozen=True)
class Freshness:
    last_export_date: date | None
    last_evaluated_at: datetime | None
    import_stale: bool
    evaluation_stale: bool


def freshness(s: Session, now: datetime, today: date | None = None) -> Freshness:
    last_export = s.scalar(select(ImportBatch.export_date).where(
        ImportBatch.status.in_(("completed", "completed_with_rejects"))).order_by(ImportBatch.export_date.desc()))
    last_eval = s.scalar(select(EvaluationRun.finished_at).where(EvaluationRun.status == "succeeded")
                         .order_by(EvaluationRun.finished_at.desc()))
    today = today or local_date_of(now)
    return Freshness(
        last_export, last_eval,
        import_stale=last_export is None or (today - last_export).days > IMPORT_STALE_DAYS,
        evaluation_stale=last_eval is None or now - last_eval > EVALUATION_STALE,
    )


def staleness_check(
    engine: Engine, clinic_id: uuid.UUID, now: datetime, alerter: Alerter = default_alerter
) -> Freshness:
    with tenant_session(engine, clinic_id) as s:
        fr = freshness(s, now)
        if fr.import_stale:
            alerter.alert(s, "import_stale", clinic_id)
        if fr.evaluation_stale:
            alerter.alert(s, "evaluation_stale", clinic_id)
        return fr
