"""Append-only audit events (T-2.2.5; MH-13). `meta` holds counts and codes, never row values."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from claimcheck_core.logging import get_correlation_id
from claimcheck_core.models import AuditEvent

_FORBIDDEN_META = {"invoice_ref", "claim_token", "amount", "date_of_service", "payload", "value", "values"}


def write_audit(
    session: Session,
    action: str,
    outcome: str,
    clinic_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None = None,
    object_type: str | None = None,
    object_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> None:
    meta = meta or {}
    bad = _FORBIDDEN_META.intersection(meta)
    if bad:
        raise ValueError("audit meta may hold counts and codes only")
    cid = correlation_id or get_correlation_id() or str(uuid.uuid4())
    session.add(AuditEvent(
        clinic_id=clinic_id, actor_user_id=actor_user_id, action=action, outcome=outcome,
        object_type=object_type, object_id=object_id, meta=meta, correlation_id=uuid.UUID(cid),
    ))


def write_global_audit(session: Session, action: str, outcome: str, actor_user_id: uuid.UUID | None = None,
                       meta: dict[str, Any] | None = None) -> None:
    """An event with no clinic (e.g. a sign-in attempt for an unknown address). Inserted without
    RETURNING, because the read policy shows clinic rows only and would refuse to return it."""
    meta = meta or {}
    if _FORBIDDEN_META.intersection(meta):
        raise ValueError("audit meta may hold counts and codes only")
    cid = get_correlation_id() or str(uuid.uuid4())
    session.execute(text(
        "INSERT INTO audit_event (clinic_id, actor_user_id, action, object_type, object_id, outcome, "
        "correlation_id, meta) VALUES (NULL, :u, :a, 'app_user', :u, :o, :c, CAST(:m AS jsonb))"),
        {"u": actor_user_id, "a": action, "o": outcome, "c": uuid.UUID(cid), "m": json.dumps(meta)})
