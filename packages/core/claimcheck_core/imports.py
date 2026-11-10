"""Import batches: create (idempotent on content hash), stage rows through the guard, finalize as a job
(T-3.1.2, T-3.1.3; MH-01, MH-02; R-01, R-19)."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Engine, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from claimcheck_core.alerts import Alerter, default_alerter
from claimcheck_core.audit import write_audit
from claimcheck_core.intake.contract import (
    ContractError,
    FieldError,
    from_json,
    missing_required,
    parse_rows,
    to_json,
)
from claimcheck_core.intake.guard import GuardFailure, check_rows
from claimcheck_core.jobs import enqueue
from claimcheck_core.logging import get_logger, log_event
from claimcheck_core.models import Claim, Clinic, ExportProfile, ImportBatch, ImportRow, Visit, VisitSnapshot
from claimcheck_core.money import cad
from claimcheck_core.settings import get_settings
from claimcheck_core.tenancy import tenant_session

_log = get_logger("imports")


class ImportsPaused(Exception):
    pass


class BatchNotReceiving(Exception):
    pass


class CountMismatch(Exception):
    def __init__(self, expected: int, staged: int) -> None:
        super().__init__("count_mismatch")
        self.expected = expected
        self.staged = staged


class GuardRejected(Exception):
    def __init__(self, failures: list[GuardFailure]) -> None:
        super().__init__("identifier_guard")
        self.failures = failures


@dataclass(frozen=True)
class BatchRef:
    id: uuid.UUID
    status: str
    created: bool


def create_batch(
    session: Session, clinic_id: uuid.UUID, user_id: uuid.UUID, content_hash: str, export_date: date,
    profile_sales_id: uuid.UUID, profile_policies_id: uuid.UUID, correlation_id: str,
) -> BatchRef:
    clinic = session.get(Clinic, clinic_id)
    if clinic is None:
        raise LookupError("clinic")
    if clinic.imports_paused_at is not None:
        raise ImportsPaused()
    existing = session.scalar(select(ImportBatch).where(ImportBatch.content_hash == content_hash))
    if existing is not None:
        return BatchRef(existing.id, existing.status, False)  # IT-02: same content, same batch
    batch = ImportBatch(
        clinic_id=clinic_id, created_by=user_id, content_hash=content_hash, export_date=export_date,
        profile_sales_id=profile_sales_id, profile_policies_id=profile_policies_id,
        correlation_id=uuid.UUID(correlation_id),
    )
    session.add(batch)
    session.flush()
    write_audit(session, "import_created", "ok", clinic_id, user_id, "import_batch", batch.id)
    return BatchRef(batch.id, batch.status, True)


def allowed_codes(session: Session, profile_sales_id: uuid.UUID) -> frozenset[str]:
    profile = session.get(ExportProfile, profile_sales_id)
    if profile is None:
        raise LookupError("profile")
    return frozenset(profile.header_map.get("billing_codes", {}).values())


def stage_rows(
    session: Session, clinic_id: uuid.UUID, batch_id: uuid.UUID, body: dict[str, Any], today: date
) -> int:
    """Validate and stage one request. Raises ContractError or GuardRejected; nothing is written then."""
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise LookupError("batch")
    if batch.status != "receiving":
        raise BatchNotReceiving()
    if set(body) - {"visits", "claims"}:
        raise ContractError([FieldError(None, "unknown_field", "not_allowed")])
    codes = allowed_codes(session, batch.profile_sales_id)
    visits = parse_rows("visit", body.get("visits", []), codes)
    claims = parse_rows("claim", body.get("claims", []), codes)
    failures = check_rows(visits, claims, today)
    if failures:
        raise GuardRejected(failures)
    for kind, rows in (("visit", visits), ("claim", claims)):
        if not rows:
            continue
        stmt = insert(ImportRow).values([
            {"clinic_id": clinic_id, "batch_id": batch_id, "row_no": r["row_no"], "kind": kind,
             "payload": to_json(r)} for r in rows
        ])
        session.execute(stmt.on_conflict_do_update(
            index_elements=["batch_id", "kind", "row_no"], set_={"payload": stmt.excluded.payload}))
    return len(visits) + len(claims)


def record_guard_rejection(
    engine: Engine, clinic_id: uuid.UUID, batch_id: uuid.UUID, failures: list[GuardFailure],
    actor: uuid.UUID | None, alerter: Alerter = default_alerter,
) -> None:
    """Separate transaction: batch -> rejected_guard, any staged rows removed, audit without values."""
    with tenant_session(engine, clinic_id) as s:
        batch = s.get(ImportBatch, batch_id, with_for_update=True)
        if batch is None:
            return
        s.execute(delete(ImportRow).where(ImportRow.batch_id == batch_id))
        batch.status = "rejected_guard"
        meta = {"checks": sorted({f.check for f in failures}), "fields": sorted({f.field for f in failures}),
                "rows": sum(f.rows for f in failures)}
        write_audit(s, "import_rejected_guard", "rejected", clinic_id, actor, "import_batch", batch_id, meta)
        alerter.alert(s, "guard_rejection", clinic_id, rows=meta["rows"])


def request_finalize(session: Session, clinic_id: uuid.UUID, batch_id: uuid.UUID, expected_rows: int) -> str:
    batch = session.get(ImportBatch, batch_id, with_for_update=True)
    if batch is None:
        raise LookupError("batch")
    if batch.status != "receiving":
        return batch.status  # safe to repeat
    staged = session.scalar(select(func.count()).select_from(ImportRow).where(ImportRow.batch_id == batch_id)) or 0
    if staged != expected_rows:
        raise CountMismatch(expected_rows, staged)
    batch.status = "processing"
    batch.expected_rows = expected_rows
    enqueue(session, clinic_id, "import_finalize", f"import_finalize:{batch_id}", {"batch_id": str(batch_id)})
    return batch.status


def _test_pause() -> None:
    """IT-10 hook: lets a test kill the worker in the middle of finalize. Only in APP_ENV=test."""
    seconds = os.environ.get("CLAIMCHECK_TEST_PAUSE_FINALIZE_S")
    if seconds and get_settings().app_env == "test":
        time.sleep(float(seconds))


def finalize(engine: Engine, clinic_id: uuid.UUID, batch_id: uuid.UUID, today: date,
             alerter: Alerter = default_alerter) -> str:
    """The import_finalize job. One transaction; a repeat after success is a no-op."""
    with tenant_session(engine, clinic_id) as s:
        batch = s.get(ImportBatch, batch_id, with_for_update=True)
        if batch is None:
            raise LookupError("batch")
        if batch.status != "processing":
            return batch.status
        rows = list(s.scalars(select(ImportRow).where(ImportRow.batch_id == batch_id)
                              .order_by(ImportRow.kind, ImportRow.row_no)))
        parsed = [(r, from_json(r.kind, r.payload)) for r in rows]
        visits_in = [p for r, p in parsed if r.kind == "visit"]
        claims_in = [p for r, p in parsed if r.kind == "claim"]
        failures = check_rows(visits_in, claims_in, today)  # whole-batch plausibility (check iii)
        if failures:
            s.execute(delete(ImportRow).where(ImportRow.batch_id == batch_id))
            batch.status = "rejected_guard"
            write_audit(s, "import_rejected_guard", "rejected", clinic_id, None, "import_batch", batch_id,
                        {"checks": sorted({f.check for f in failures}), "rows": sum(f.rows for f in failures)})
            alerter.alert(s, "guard_rejection", clinic_id, rows=sum(f.rows for f in failures))
            return batch.status

        accepted: list[tuple[str, dict[str, Any]]] = []
        rejected = duplicate = 0
        seen_v: set[tuple[str, int]] = set()
        seen_c: set[tuple[str, str]] = set()
        for row, p in parsed:
            if missing_required(row.kind, p):
                row.reject_reason = "missing_required"
                rejected += 1
                continue
            key_v = (p["invoice_ref"], p["line_no"]) if row.kind == "visit" else None
            key_c = (p["claim_token"], p["payer"]) if row.kind == "claim" else None
            if (key_v and key_v in seen_v) or (key_c and key_c in seen_c):
                row.reject_reason = "duplicate_row"
                duplicate += 1
                continue
            if key_v:
                seen_v.add(key_v)
            if key_c:
                seen_c.add(key_c)
            accepted.append((row.kind, p))

        claim_ids = _upsert_claims(s, clinic_id, batch, [p for k, p in accepted if k == "claim"],
                                   [p for k, p in accepted if k == "visit"])
        _upsert_visits(s, clinic_id, batch, [p for k, p in accepted if k == "visit"], claim_ids)
        _test_pause()

        batch.rows_received = len(rows)
        batch.rows_accepted = len(accepted)
        batch.rows_rejected = rejected
        batch.rows_duplicate = duplicate
        if batch.expected_rows is not None and batch.expected_rows != len(rows):
            batch.status = "failed"
            write_audit(s, "import_failed", "count_mismatch", clinic_id, None, "import_batch", batch_id)
            return batch.status
        batch.status = "completed" if rejected + duplicate == 0 else "completed_with_rejects"
        batch.completed_at = datetime.now(tz=UTC)
        enqueue(s, clinic_id, "evaluate_clinic", f"evaluate_clinic:{clinic_id}:batch:{batch_id}",
                {"trigger": "import", "batch_id": str(batch_id)})
        counts = {"received": len(rows), "accepted": len(accepted), "rejected": rejected, "duplicate": duplicate}
        write_audit(s, "import_completed", batch.status, clinic_id, None, "import_batch", batch_id, counts)
        log_event(_log, "import_finalized", batch_id=str(batch_id), **counts)
        return batch.status


def _upsert_claims(
    s: Session, clinic_id: uuid.UUID, batch: ImportBatch, claim_rows: list[dict[str, Any]],
    visit_rows: list[dict[str, Any]],
) -> dict[tuple[str, str], uuid.UUID]:
    existing: dict[tuple[str, str], tuple[Claim, date]] = {}
    for c, export_date in s.execute(select(Claim, ImportBatch.export_date).join(
            ImportBatch, ImportBatch.id == Claim.last_batch_id)):
        existing[(c.claim_token, c.payer)] = (c, export_date)
    fields = ("policy_status", "end_date", "treatments_count", "policy_max", "next_appointment_date", "date_of_event")
    for p in claim_rows:
        key = (p["claim_token"], p["payer"])
        if key in existing:
            c, last_export = existing[key]
            if batch.export_date >= last_export:  # an older export never overwrites newer state (R-01)
                for f in fields:
                    setattr(c, f, p.get(f))
                c.last_batch_id = batch.id
                c.updated_at = datetime.now(tz=UTC)
                existing[key] = (c, batch.export_date)
        else:
            c = Claim(clinic_id=clinic_id, claim_token=p["claim_token"], payer=p["payer"], last_batch_id=batch.id,
                      **{f: p.get(f) for f in fields})
            s.add(c)
            existing[key] = (c, batch.export_date)
    # A visit may name a claim that the Policies export did not carry: keep the link without details.
    for p in visit_rows:
        token = p.get("claim_token")
        if token and (token, p["payer"]) not in existing:
            c = Claim(clinic_id=clinic_id, claim_token=token, payer=p["payer"], last_batch_id=batch.id)
            s.add(c)
            existing[(token, p["payer"])] = (c, batch.export_date)
    s.flush()
    return {k: v[0].id for k, v in existing.items()}


def _upsert_visits(
    s: Session, clinic_id: uuid.UUID, batch: ImportBatch, rows: list[dict[str, Any]],
    claim_ids: dict[tuple[str, str], uuid.UUID],
) -> None:
    existing = {(v.invoice_ref, v.line_no): v for v in s.scalars(select(Visit))}
    pending: list[tuple[Visit, dict[str, Any]]] = []
    for p in rows:
        state = p["submission_state"]
        paid = cad(p.get("amount_paid") or 0)
        invoiced = cad(p["amount_invoiced"])
        claim_id = claim_ids.get((p["claim_token"], p["payer"])) if p.get("claim_token") else None
        rejected_on = p.get("state_date") if state == "rejected" else None
        snap = {"submission_state": state, "amount_invoiced": invoiced, "amount_paid": paid,
                "state_date": p.get("state_date")}
        v = existing.get((p["invoice_ref"], p["line_no"]))
        changed = True
        if v is None:
            v = Visit(clinic_id=clinic_id, invoice_ref=p["invoice_ref"], line_no=p["line_no"], claim_id=claim_id,
                      payer=p["payer"], discipline=p["discipline"], date_of_service=p["date_of_service"],
                      billing_code=p["billing_code"], amount_invoiced=invoiced, amount_paid=paid,
                      submission_state=state, state_date=p.get("state_date"), first_rejected_on=rejected_on,
                      first_seen_batch_id=batch.id, first_seen_export_date=batch.export_date,
                      last_batch_id=batch.id, last_export_date=batch.export_date)
            s.add(v)
            existing[(v.invoice_ref, v.line_no)] = v
        else:
            if rejected_on is not None and (v.first_rejected_on is None or rejected_on < v.first_rejected_on):
                v.first_rejected_on = rejected_on  # earliest rejection date Jane exported
            if batch.export_date < v.first_seen_export_date:
                v.first_seen_export_date = batch.export_date
            if batch.export_date >= v.last_export_date:
                changed = (v.submission_state, v.amount_invoiced, v.amount_paid, v.state_date) != tuple(snap.values())
                v.claim_id, v.payer, v.discipline = claim_id, p["payer"], p["discipline"]
                v.date_of_service, v.billing_code = p["date_of_service"], p["billing_code"]
                v.amount_invoiced, v.amount_paid, v.submission_state = invoiced, paid, state
                v.state_date = p.get("state_date")
                v.last_batch_id, v.last_export_date = batch.id, batch.export_date
            # an older export: snapshot stored for history, current state untouched (IT-05)
        if changed:
            pending.append((v, snap))
    s.flush()
    already = set(s.scalars(select(VisitSnapshot.visit_id).where(VisitSnapshot.batch_id == batch.id)))
    for v, snap in pending:
        if v.id not in already:
            s.add(VisitSnapshot(clinic_id=clinic_id, visit_id=v.id, batch_id=batch.id,
                                export_date=batch.export_date, **snap))
    s.flush()
