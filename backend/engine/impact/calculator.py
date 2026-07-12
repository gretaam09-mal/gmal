"""Quantifies a bound obligation's cost — pure, deterministic, no I/O.

CONVENTIONS.md rule #1: this is the only place a cost figure is computed.
services/analyses.py calls compute_impact once a predicate BINDS and its
obligation has a CostTemplate; the LLM never touches this number.

Formula shape (CostTemplate.formula — see db/models/regulatory.py):
    {"base": 5000, "terms": [{"driver": "scale.employee_count", "rate": 40}]}
amount = base + sum(rate * facts[driver] for each term). If any driver is
missing from facts, the amount is unavailable (None) rather than silently
treated as zero — a missing input should never look like "no cost".
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class ImpactResult:
    amount: Decimal | None
    currency: str = "GBP"
    missing_driver_keys: tuple[str, ...] = ()


def compute_impact(
    formula: dict[str, Any], facts: dict[str, Any], *, currency: str = "GBP"
) -> ImpactResult:
    base = Decimal(str(formula.get("base", 0)))
    terms = formula.get("terms", [])

    missing = tuple(
        sorted({term["driver"] for term in terms if facts.get(term["driver"]) is None})
    )
    if missing:
        return ImpactResult(amount=None, currency=currency, missing_driver_keys=missing)

    total = base
    for term in terms:
        rate = Decimal(str(term["rate"]))
        value = Decimal(str(facts[term["driver"]]))
        total += rate * value
    return ImpactResult(amount=total, currency=currency)


_BANDS: tuple[tuple[Decimal | None, str], ...] = (
    (Decimal(10_000), "< £10k"),
    (Decimal(50_000), "£10k–£50k"),
    (Decimal(250_000), "£50k–£250k"),
    (None, "£250k+"),
)


def impact_band(amount: Decimal | None) -> str:
    """A coarse, deterministic display bucket for the Exposure List — never
    the number itself, just a band so an unconfirmed estimate doesn't read
    as false precision."""
    if amount is None:
        return "Unknown"
    for ceiling, label in _BANDS:
        if ceiling is None or amount < ceiling:
            return label
    return _BANDS[-1][1]
