"""B1 API for the core path: imports, lists, item detail and outcomes, pilot escape count."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, select

from claimcheck_api.deps import ApiError, Principal, engine_dep, owner_dep, principal_dep, today_dep
from claimcheck_core.alerts import default_alerter
from claimcheck_core.audit import write_audit
from claimcheck_core.evaluation import freshness
from claimcheck_core.imports import (
    BatchNotReceiving,
    CountMismatch,
    GuardRejected,
    ImportsPaused,
    create_batch,
    record_guard_rejection,
    request_finalize,
    stage_rows,
)
from claimcheck_core.intake.contract import ContractError
from claimcheck_core.intake.guard import GuardFailure
from claimcheck_core.lists import banner, reasons, summary_sentence, week_counts
from claimcheck_core.logging import get_correlation_id
from claimcheck_core.models import AuditEvent, ExportProfile, Finding, ImportBatch, ImportRow, Item, Visit
from claimcheck_core.money import ZERO, cad
from claimcheck_core.outcomes import InvalidEvent, StaleVersion, record_event
from claimcheck_core.payloads import read_payload
from claimcheck_core.storage import ObjectMissing, get_store
from claimcheck_core.tenancy import tenant_session

router = APIRouter(prefix="/api/v1")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_ROWS_PER_REQUEST = 500


class CreateImport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    export_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    profile_sales_version: int = Field(ge=1)
    profile_policies_version: int = Field(ge=1)


class Finalize(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_rows: int = Field(ge=0, le=100_000)


class ItemEventIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: str = Field(pattern=r"^(outcome|undone|reopened)$")
    outcome: str | None = Field(default=None, pattern=r"^[a-z_]{1,40}$")
    reason_code: str | None = Field(default=None, pattern=r"^[a-z_]{1,40}$")
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9-]{8,64}$")


def _not_found(engine: Engine, p: Principal, object_type: str, object_id: uuid.UUID) -> ApiError:
    # RLS returns no row for another clinic's object; it is reported as 404, never 403 (MH-10 c).
    with tenant_session(engine, p.clinic_id) as s:
        write_audit(s, "cross_clinic_denied", "not_found", p.clinic_id, p.user_id, object_type, object_id)
        default_alerter.alert(s, "cross_clinic_denied", p.clinic_id)
    return ApiError(404, "not_found", "Not found.")


# ------------------------------------------------------------------ imports


@router.post("/imports", status_code=201)
def post_import(body: CreateImport, response: Response, idempotency_key: str = Header(alias="Idempotency-Key"),
                p: Principal = Depends(principal_dep), engine: Engine = Depends(engine_dep)) -> dict[str, Any]:
    if not HASH_RE.match(idempotency_key):
        raise ApiError(422, "invalid_request", "Idempotency-Key must be the SHA-256 of the minimised content.")
    with tenant_session(engine, p.clinic_id) as s:
        profiles = {(r.report, r.version): r.id for r in s.scalars(
            select(ExportProfile).where(ExportProfile.published_at.isnot(None)))}
        sales = profiles.get(("sales", body.profile_sales_version))
        pol = profiles.get(("policies", body.profile_policies_version))
        if not sales or not pol:
            raise ApiError(422, "unknown_profile", "This export profile is not published.")
        try:
            ref = create_batch(s, p.clinic_id, p.user_id, idempotency_key, date.fromisoformat(body.export_date),
                               sales, pol, get_correlation_id() or str(uuid.uuid4()))
        except ImportsPaused:
            raise ApiError(409, "imports_paused",
                           "Imports are paused for this clinic while we review a check.") from None
    if not ref.created:
        response.status_code = 200
    return {"id": str(ref.id), "status": ref.status, "created": ref.created}


@router.post("/imports/{batch_id}/rows")
async def post_rows(batch_id: uuid.UUID, request: Request, p: Principal = Depends(principal_dep),
                    engine: Engine = Depends(engine_dep), today: date = Depends(today_dep)) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError:
        raise ApiError(422, "invalid_request", "Body must be JSON.") from None
    if not isinstance(body, dict):
        raise ApiError(422, "invalid_request", "Body must be an object.")
    n_rows = sum(len(v) for v in body.values() if isinstance(v, list))
    if n_rows > MAX_ROWS_PER_REQUEST:
        raise ApiError(413, "too_many_rows", "Send at most 500 rows per request.")
    try:
        with tenant_session(engine, p.clinic_id) as s:
            staged = stage_rows(s, p.clinic_id, batch_id, body, today)
    except LookupError:
        raise _not_found(engine, p, "import_batch", batch_id) from None
    except BatchNotReceiving:
        raise ApiError(409, "batch_closed", "This import is no longer receiving rows.") from None
    except ContractError as exc:
        # The whole request is refused; the batch is closed so nothing from it is ever stored.
        fails = [GuardFailure("schema", e.field, 1) for e in exc.errors]
        record_guard_rejection(engine, p.clinic_id, batch_id, fails, p.user_id)
        fields = [{"row_no": e.row_no, "field": e.field, "code": e.code} for e in exc.errors[:50]]
        raise ApiError(422, "identifier_guard", "Nothing was uploaded. Jane's export looks different.",
                       fields) from None
    except GuardRejected as exc:
        record_guard_rejection(engine, p.clinic_id, batch_id, exc.failures, p.user_id)
        fields = [{"row_no": None, "field": f.field, "code": f.check} for f in exc.failures]
        raise ApiError(422, "identifier_guard", "Nothing was uploaded. Jane's export looks different.",
                       fields) from None
    return {"staged": staged}


@router.post("/imports/{batch_id}/finalize", status_code=202)
def post_finalize(batch_id: uuid.UUID, body: Finalize, p: Principal = Depends(principal_dep),
                  engine: Engine = Depends(engine_dep)) -> dict[str, Any]:
    try:
        with tenant_session(engine, p.clinic_id) as s:
            status = request_finalize(s, p.clinic_id, batch_id, body.expected_rows)
    except LookupError:
        raise _not_found(engine, p, "import_batch", batch_id) from None
    except CountMismatch as exc:
        raise ApiError(409, "count_mismatch", "Some rows have not arrived yet; resume the upload.",
                       [{"expected": exc.expected, "staged": exc.staged}]) from None
    return {"id": str(batch_id), "status": status}


@router.get("/imports/{batch_id}")
def get_import(batch_id: uuid.UUID, p: Principal = Depends(principal_dep),
               engine: Engine = Depends(engine_dep)) -> dict[str, Any]:
    with tenant_session(engine, p.clinic_id) as s:
        b = s.get(ImportBatch, batch_id)
        if b is None:
            raise _not_found(engine, p, "import_batch", batch_id)
        rejected = [{"kind": r.kind, "row_no": r.row_no, "reason": r.reject_reason} for r in s.scalars(
            select(ImportRow).where(ImportRow.batch_id == batch_id, ImportRow.reject_reason.isnot(None))
            .order_by(ImportRow.kind, ImportRow.row_no))]
        return {"id": str(b.id), "status": b.status, "export_date": b.export_date.isoformat(),
                "rows_received": b.rows_received, "rows_accepted": b.rows_accepted,
                "rows_rejected": b.rows_rejected, "rows_duplicate": b.rows_duplicate, "rejected_rows": rejected}


@router.get("/imports/{batch_id}/payload")
def get_import_payload(batch_id: uuid.UUID, p: Principal = Depends(principal_dep),
                       engine: Engine = Depends(engine_dep)) -> Response:
    """B2 (AD-11): the minimised payload as stored, for the batch's own clinic only. The object key is
    read under row-level security and the store is bound to the caller's clinic prefix."""
    with tenant_session(engine, p.clinic_id) as s:
        b = s.get(ImportBatch, batch_id)
        if b is None:
            raise _not_found(engine, p, "import_batch", batch_id)
        key, deleted = b.payload_object_key, b.payload_deleted_at
    if key is None or deleted is not None:
        raise ApiError(404, "payload_not_kept", "This import's rows are not kept any more.")
    try:
        data = read_payload(get_store(), p.clinic_id, key)
    except ObjectMissing:
        raise ApiError(404, "payload_not_kept", "This import's rows are not kept any more.") from None
    except PermissionError:
        # B2-S04: a stored key outside the caller's clinic prefix is a tampering signal: 404, audit, alert.
        raise _not_found(engine, p, "import_batch", batch_id) from None
    with tenant_session(engine, p.clinic_id) as s:
        write_audit(s, "import_payload_downloaded", "ok", p.clinic_id, p.user_id, "import_batch", batch_id,
                    {"bytes": len(data)})
    return Response(content=data, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="import-{batch_id}.json"'})


# ------------------------------------------------------------------ lists

GROUP_ORDER = ["could_not_check", "deadline_14_days", "can_still_be_collected", "check_before_next_visit",
               "probably_lost", "lost", "jane_setup"]
OPEN_STATUSES = ("open", "awaiting_confirmation")


def _group(item: Item, today: date) -> str:
    if item.money_class == "permanent_certain":
        return "lost"
    if item.money_class == "permanent_discretionary":
        return "probably_lost"
    if item.money_class == "admin_time":
        return "jane_setup"
    if item.money_class == "warning":
        return "check_before_next_visit"
    if item.limit_date is not None and (item.limit_date - today).days <= 14:
        return "deadline_14_days"
    return "can_still_be_collected"


def _item_row(i: Item, v: Visit | None, f: Finding | None, today: date) -> dict[str, Any]:
    return {
        "id": str(i.id), "rule_code": i.rule_code, "reason": f.reason_code if f else None,
        "invoice_ref": v.invoice_ref if v else None, "payer": v.payer if v else None,
        "date_of_service": v.date_of_service.isoformat() if v else None,
        "limit_date": i.limit_date.isoformat() if i.limit_date else None,
        "submit_by": f.submit_by.isoformat() if f and f.submit_by else None,
        # B1-010: when set, the true limit lies between limit_date ("act by") and this date.
        "latest_limit_date": f.latest_limit_date.isoformat() if f and f.latest_limit_date else None,
        "days_left": (i.limit_date - today).days if i.limit_date else None,
        "amount": str(i.amount) if i.amount is not None else None, "money_class": i.money_class,
        "status": i.status, "version": i.version,
        "near_limit_since": i.reached_near_limit_on.isoformat() if i.reached_near_limit_on else None,
    }


@router.get("/items")
def get_items(view: str = "week", p: Principal = Depends(principal_dep), engine: Engine = Depends(engine_dep),
              today: date = Depends(today_dep)) -> dict[str, Any]:
    if view != "week":
        raise ApiError(422, "invalid_request", "Only view=week exists in this build.")
    with tenant_session(engine, p.clinic_id) as s:
        fr = freshness(s, datetime.now(tz=UTC), today)
        wc = week_counts(s)
        rows = s.execute(
            select(Item, Visit, Finding).outerjoin(Visit, Visit.id == Item.visit_id).outerjoin(
                Finding, (Finding.rule_code == Item.rule_code) & (
                    (Finding.visit_id == Item.visit_id) | (Finding.claim_id == Item.claim_id)))
            .where(Item.status.in_(OPEN_STATUSES))
            .order_by(Item.limit_date.asc().nulls_last(), Item.id)).all()
        groups: dict[str, list[dict[str, Any]]] = {g: [] for g in GROUP_ORDER}
        totals: dict[str, dict[str, Any]] = {}
        for i, v, f in rows:
            groups[_group(i, today)].append(_item_row(i, v, f, today))
            t = totals.setdefault(i.money_class, {"count": 0, "amount": ZERO})
            t["count"] += 1
            t["amount"] = cad(t["amount"] + (i.amount or Decimal(0)))
        groups["could_not_check"] = wc.not_checked_rows
    open_items = sum(len(groups[g]) for g in GROUP_ORDER if g != "could_not_check")
    summary = summary_sentence(wc, open_items, fr.last_evaluated_at is not None)
    return {
        "counts": wc.as_dict(), "could_not_check_reasons": reasons(wc),
        "totals": {k: {"count": v["count"], "amount": str(v["amount"])} for k, v in sorted(totals.items())},
        "groups": groups, "summary": summary, "banner": banner(wc),
        "freshness": {
            "last_export_date": fr.last_export_date.isoformat() if fr.last_export_date else None,
            "last_evaluated_at": fr.last_evaluated_at.isoformat() if fr.last_evaluated_at else None,
            "import_stale": fr.import_stale, "evaluation_stale": fr.evaluation_stale,
        },
    }


@router.get("/items/{item_id}")
def get_item(item_id: uuid.UUID, p: Principal = Depends(principal_dep), engine: Engine = Depends(engine_dep),
             today: date = Depends(today_dep)) -> dict[str, Any]:
    with tenant_session(engine, p.clinic_id) as s:
        i = s.get(Item, item_id)
        if i is None:
            raise _not_found(engine, p, "item", item_id)
        v = s.get(Visit, i.visit_id) if i.visit_id else None
        target = Finding.visit_id == i.visit_id if i.visit_id else Finding.claim_id == i.claim_id
        findings = [{"rule_code": f.rule_code, "outcome": f.outcome, "reason": f.reason_code,
                     "limit_date": f.limit_date.isoformat() if f.limit_date else None,
                     "rule_version_id": str(f.rule_version_id) if f.rule_version_id else None}
                    for f in s.scalars(select(Finding).where(target).order_by(Finding.rule_code))]
        own = next((f for f in s.scalars(select(Finding).where(target, Finding.rule_code == i.rule_code))), None)
        return {**_item_row(i, v, own, today), "findings": findings}


@router.post("/items/{item_id}/events")
def post_item_event(item_id: uuid.UUID, body: ItemEventIn, if_match: str = Header(alias="If-Match"),
                    p: Principal = Depends(principal_dep), engine: Engine = Depends(engine_dep)) -> dict[str, Any]:
    if not if_match.isdigit():
        raise ApiError(428, "if_match_required", "Send the item version you saw.")
    try:
        with tenant_session(engine, p.clinic_id) as s:
            r = record_event(s, p.clinic_id, item_id, p.user_id, body.kind, body.outcome, body.reason_code,
                             body.idempotency_key, int(if_match))
    except LookupError:
        raise _not_found(engine, p, "item", item_id) from None
    except StaleVersion:
        raise ApiError(409, "stale_version", "Someone else changed this item. Reload it.") from None
    except InvalidEvent as exc:
        raise ApiError(422, "invalid_event", "Choose an outcome from the list.", [{"field": str(exc)}]) from None
    return {"id": str(r.item_id), "status": r.status, "version": r.version, "replayed": r.replayed}


@router.get("/pilot-report")
def get_pilot_report(p: Principal = Depends(owner_dep), engine: Engine = Depends(engine_dep)) -> dict[str, Any]:
    """B1 subset of S-10: M-09 escapes only (T-5.1.1 is not built)."""
    with tenant_session(engine, p.clinic_id) as s:
        ids = sorted({e for e in s.scalars(select(AuditEvent.object_id).where(AuditEvent.action == "m09_escape"))
                      if e is not None}, key=str)
        visits = {v.id: v for v in s.scalars(select(Visit).where(Visit.id.in_(ids)))} if ids else {}
        escapes = [{"visit_id": str(i), "invoice_ref": visits[i].invoice_ref if i in visits else None} for i in ids]
    return {"m09_escapes": len(escapes), "escapes": escapes}
