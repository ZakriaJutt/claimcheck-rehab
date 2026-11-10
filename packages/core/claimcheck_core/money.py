"""Money as Decimal with two places, CAD (numeric(10,2)). No floating point anywhere."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def cad(value: Decimal | int | str) -> Decimal:
    if isinstance(value, float):  # pragma: no cover - defensive
        raise TypeError("float money is not allowed")
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def total(values: list[Decimal]) -> Decimal:
    return cad(sum(values, ZERO))
