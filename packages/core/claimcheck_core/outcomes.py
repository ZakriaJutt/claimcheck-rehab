"""Staff outcomes on items, with optimistic concurrency and idempotency keys (T-4.2.2; MH-07; IT-07, IT-08).

No free text: the outcome and the reason are chosen from fixed lists.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from claimcheck_core.audit import write_audit
from claimcheck_core.models import Item, ItemEvent

OUTCOME_STATUS = {
    "submitted": "awaiting_confirmation",
    "verified_in_portal": "awaiting_confirmation",
    "corrected_resubmitted": "awaiting_confirmation",
    "treatment_plan_requested": "awaiting_confirmation",
    "portal_not_received": "open",  # ICBC-01 applies from the next evaluation
    "written_off": "written_off",
    "not_an_error": "dismissed",
}
REASONS = frozenset({"already_paid", "payer_approved", "duplicate_row", "rule_wrong", "not_our_claim", "other"})


class StaleVersion(Exception):
    pass


class InvalidEvent(Exception):
    pass


@dataclass(frozen=True)
class EventResult:
    item_id: uuid.UUID
    status: str
    version: int
    replayed: bool


def record_event(
    s: Session, clinic_id: uuid.UUID, item_id: uuid.UUID, actor: uuid.UUID, kind: str,
    outcome: str | None, reason_code: str | None, idempotency_key: str, if_match: int,
) -> EventResult:
    item = s.get(Item, item_id)
    if item is None:
        raise LookupError("item")
    prior = s.scalar(select(ItemEvent).where(ItemEvent.item_id == item_id,
                                             ItemEvent.idempotency_key == idempotency_key))
    if prior is not None:
        return EventResult(item.id, item.status, item.version, True)
    if kind == "outcome":
        if outcome not in OUTCOME_STATUS:
            raise InvalidEvent("outcome")
        if outcome == "not_an_error" and reason_code not in REASONS:
            raise InvalidEvent("reason_code")
        if outcome != "not_an_error" and reason_code is not None:
            raise InvalidEvent("reason_code")
        status = OUTCOME_STATUS[outcome]
    elif kind in ("undone", "reopened"):
        if outcome is not None or reason_code is not None:
            raise InvalidEvent("outcome")
        status = "open"
    else:
        raise InvalidEvent("kind")
    n = s.execute(update(Item).where(Item.id == item_id, Item.version == if_match)
                  .values(status=status, version=Item.version + 1)).rowcount  # type: ignore[attr-defined]
    if n != 1:
        raise StaleVersion()
    s.add(ItemEvent(clinic_id=clinic_id, item_id=item_id, actor_user_id=actor, kind=kind, outcome=outcome,
                    reason_code=reason_code, idempotency_key=idempotency_key))
    write_audit(s, "item_event", kind, clinic_id, actor, "item", item_id, {"outcome": outcome})
    return EventResult(item_id, status, if_match + 1, False)
