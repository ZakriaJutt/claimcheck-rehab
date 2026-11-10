"""Job runner primitives over PostgreSQL (AD-05; T-2.2.6; R-01, R-02).

Claim with a lease (FOR UPDATE SKIP LOCKED inside cc_job_claim); complete only where
status = 'running' AND lease_token = :mine, so a late or duplicate completion updates zero rows.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from claimcheck_core.logging import get_correlation_id, get_logger, log_event
from claimcheck_core.models import Job
from claimcheck_core.tenancy import system_session

_log = get_logger("jobs")


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    clinic_id: uuid.UUID | None
    kind: str
    idempotency_key: str
    attempt: int
    lease_token: uuid.UUID
    correlation_id: uuid.UUID
    payload: dict[str, Any]


def enqueue(session: Session, clinic_id: uuid.UUID, kind: str, key: str, payload: dict[str, Any] | None = None,
            max_attempts: int = 3) -> None:
    """Enqueue inside the caller's tenant transaction; idempotent on the key."""
    cid = get_correlation_id() or str(uuid.uuid4())
    stmt = insert(Job).values(clinic_id=clinic_id, kind=kind, idempotency_key=key, payload=payload or {},
                              correlation_id=uuid.UUID(cid), max_attempts=max_attempts)
    session.execute(stmt.on_conflict_do_nothing(index_elements=["idempotency_key"]))


def claim_next(engine: Engine, lease_seconds: int, kinds: list[str] | None = None) -> ClaimedJob | None:
    lease = uuid.uuid4()
    with system_session(engine) as s:
        row = s.execute(text("SELECT * FROM cc_job_claim(:l, :s, :k)"),
                        {"l": lease, "s": lease_seconds, "k": kinds}).mappings().first()
    if row is None:
        return None
    return ClaimedJob(row["id"], row["clinic_id"], row["kind"], row["idempotency_key"], row["attempt"],
                      lease, row["correlation_id"], row["payload"])


def complete(engine: Engine, job_id: uuid.UUID, lease: uuid.UUID, ok: bool, error_code: str | None = None,
             retryable: bool = True) -> int:
    with system_session(engine) as s:
        n = int(s.execute(text("SELECT cc_job_complete(:j, :l, :ok, :e, :r)"),
                          {"j": job_id, "l": lease, "ok": ok, "e": error_code, "r": retryable}).scalar_one())
    if n == 0:
        log_event(_log, "job_completion_ignored", job_id=str(job_id), reason="stale_lease_or_state")
    return n


def expire_leases(engine: Engine) -> int:
    with system_session(engine) as s:
        return int(s.execute(text("SELECT cc_job_expire_leases()")).scalar_one())


def enqueue_per_clinic(engine: Engine, kind: str, key_suffix: str, payload: dict[str, Any]) -> int:
    cid = get_correlation_id() or str(uuid.uuid4())
    with system_session(engine) as s:
        return int(s.execute(text("SELECT cc_enqueue_per_clinic(:k, :sfx, CAST(:p AS jsonb), :c)"),
                             {"k": kind, "sfx": key_suffix, "p": _json(payload), "c": cid}).scalar_one())


def _json(obj: dict[str, Any]) -> str:
    import json
    return json.dumps(obj, sort_keys=True)
