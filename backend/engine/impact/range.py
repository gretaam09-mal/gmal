"""Best/likely/worst range around compute_impact's point value — pure, no I/O.

See engine/__init__.py: deterministic, no LLM arithmetic.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from engine.impact.calculator import compute_impact

_DEFAULT_LOW_MULTIPLIER = Decimal("0.8")
_DEFAULT_HIGH_MULTIPLIER = Decimal("1.3")


@dataclass(frozen=True)
class RangeResult:
    best: Decimal | None
    likely: Decimal | None
    worst: Decimal | None
    currency: str = "GBP"
    missing_driver_keys: tuple[str, ...] = ()


def compute_range(formula: dict, facts: dict, *, currency: str = "GBP") -> RangeResult:
    likely_result = compute_impact(formula, facts, currency=currency)
    if likely_result.amount is None:
        return RangeResult(
            best=None,
            likely=None,
            worst=None,
            currency=currency,
            missing_driver_keys=likely_result.missing_driver_keys,
        )
    range_cfg = formula.get("range") or {}
    low_multiplier = Decimal(str(range_cfg.get("low_multiplier", _DEFAULT_LOW_MULTIPLIER)))
    high_multiplier = Decimal(str(range_cfg.get("high_multiplier", _DEFAULT_HIGH_MULTIPLIER)))
    likely = likely_result.amount
    return RangeResult(
        best=likely * low_multiplier,
        likely=likely,
        worst=likely * high_multiplier,
        currency=currency,
    )
