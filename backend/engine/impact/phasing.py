"""Time-phasing a total impact figure over its transition period — pure, no I/O.

See engine/__init__.py: deterministic, no LLM arithmetic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class PhaseEntry:
    period: str
    amount: Decimal


def phase_schedule(
    total: Decimal | None,
    *,
    first_obligation_date: date | None,
    transition_months: int,
    analysis_date: date,
) -> tuple[PhaseEntry, ...]:
    if total is None:
        return ()
    start = first_obligation_date or analysis_date
    period_count = max(int(transition_months), 0) + 1
    periods = _month_sequence(start, period_count)
    base_amount = (total / period_count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    amounts = [base_amount] * period_count
    # A single period absorbs the rounding remainder so entries always sum
    # exactly to `total` — a property test enforces this.
    amounts[-1] += total - base_amount * period_count
    return tuple(
        PhaseEntry(period=period, amount=amount)
        for period, amount in zip(periods, amounts, strict=True)
    )


def _month_sequence(start: date, count: int) -> list[str]:
    periods = []
    year, month = start.year, start.month
    for _ in range(count):
        periods.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return periods
