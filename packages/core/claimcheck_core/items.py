"""Item lifecycle from one evaluation result (pure; T-4.1.4, MH-04 c, MH-07, MH-08 b).

- A flag opens an item (or re-opens a cleared one); its class follows today's result, so an item
  crossing its limit changes class on limit + 1 (event `class_changed`).
- `reached_near_limit_on`, `first_flagged_on` and `class_at_first_flag` are written once (a database
  trigger also enforces this).
- `awaiting_confirmation` (staff recorded an outcome) is confirmed only by a later export that clears
  the rule; if the later export still flags, the item reopens. For ICBC deadline items, Jane's
  "Submitted" mark alone never confirms: a recorded payment or "verified in ICBC's portal" is needed
  (MH-07 e).
- `not_evaluated` never clears or confirms an item: no evidence is not good news.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from claimcheck_core.money import ZERO
from claimcheck_core.rules.payer_rules import NEAR_LIMIT_RULES
from claimcheck_core.rules.types import MoneyClass, Result, VisitIn

ICBC_DEADLINE_ITEMS = frozenset({"ICBC-01", "ICBC-07"})


@dataclass(frozen=True)
class ItemState:
    rule_code: str
    status: str
    money_class: MoneyClass
    amount: Decimal | None
    limit_date: date | None
    first_flagged_on: date
    class_at_first_flag: MoneyClass
    reached_near_limit_on: date | None = None
    version: int = 1


def _confirmable(rule_code: str, visit: VisitIn | None) -> bool:
    if rule_code in ICBC_DEADLINE_ITEMS and visit is not None:
        return visit.amount_paid > ZERO or visit.portal_status == "verified"
    return True


def next_item(
    existing: ItemState | None,
    res: Result,
    on_date: date,
    visit: VisitIn | None = None,
    export_newer_than_outcome: bool = False,
) -> tuple[ItemState | None, list[str]]:
    """Return the new item state (None = no item) and the item_event kinds to append."""
    if res.outcome == "flag":
        assert res.money_class is not None
        near = res.near_limit and res.rule_code in NEAR_LIMIT_RULES
        if existing is None:
            return ItemState(
                rule_code=res.rule_code, status="open", money_class=res.money_class, amount=res.amount,
                limit_date=res.limit_date, first_flagged_on=on_date, class_at_first_flag=res.money_class,
                reached_near_limit_on=on_date if near else None,
            ), ["flagged"]
        events: list[str] = []
        status = existing.status
        if status in ("auto_cleared", "confirmed") or (status == "awaiting_confirmation" and export_newer_than_outcome):
            status = "open"
            events.append("reopened")
        if res.money_class != existing.money_class:
            events.append("class_changed")
        reached = existing.reached_near_limit_on or (on_date if near else None)
        new = replace(existing, status=status, money_class=res.money_class, amount=res.amount,
                      limit_date=res.limit_date or existing.limit_date, reached_near_limit_on=reached)
        if new != existing:
            new = replace(new, version=existing.version + 1)
        return new, events
    if existing is None or res.outcome == "not_evaluated":
        return existing, []
    # res.outcome == "clear"
    if existing.status == "open":
        return replace(existing, status="auto_cleared", version=existing.version + 1), ["auto_cleared"]
    if existing.status == "awaiting_confirmation" and export_newer_than_outcome and _confirmable(
        existing.rule_code, visit
    ):
        return replace(existing, status="confirmed", version=existing.version + 1), ["confirmed"]
    return existing, []
