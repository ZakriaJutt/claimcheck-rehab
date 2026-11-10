"""Operator alerts behind an interface (no SMS or email provider in B1). The default implementation
records an audit event `operator_alert` with a kind code and counts, and logs it."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from sqlalchemy.orm import Session

from claimcheck_core.audit import write_audit
from claimcheck_core.logging import get_logger, log_event

ALERT_KINDS = frozenset({
    "guard_rejection", "identifier_scan_match", "cross_clinic_denied", "m09_escape",
    "could_not_check_share", "evaluation_stale", "import_stale", "job_dead",
})

_log = get_logger("alerts")


class Alerter(Protocol):
    def alert(self, session: Session, kind: str, clinic_id: uuid.UUID | None, **counts: Any) -> None: ...


class AuditAlerter:
    def alert(self, session: Session, kind: str, clinic_id: uuid.UUID | None, **counts: Any) -> None:
        if kind not in ALERT_KINDS:
            raise ValueError("unknown alert kind")
        write_audit(session, "operator_alert", kind, clinic_id, meta={"kind": kind, **counts})
        log_event(_log, "operator_alert", kind=kind, clinic_id=str(clinic_id) if clinic_id else None, **counts)


default_alerter: Alerter = AuditAlerter()
