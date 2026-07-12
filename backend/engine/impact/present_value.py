"""Present-value discounting of a phased schedule — pure, no I/O.

Both the discount rate and the FX rate are declared inputs (see
Analysis.discount_rate_pct/fx_rate) — this never fetches a live rate;
see engine/__init__.py: deterministic, no LLM arithmetic.
"""
from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal


def discount_to_present_value(
    phased_amounts: Sequence[Decimal],
    *,
    discount_rate_pct: Decimal,
    fx_rate: Decimal = Decimal("1"),
) -> Decimal:
    rate = Decimal(str(discount_rate_pct)) / Decimal("100")
    total = Decimal("0")
    for period_index, amount in enumerate(phased_amounts):
        discount_factor = (Decimal("1") + rate) ** period_index
        total += amount / discount_factor
    return total * Decimal(str(fx_rate))
