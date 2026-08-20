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


def range_from_estimate(
    *, best: Decimal, likely: Decimal, worst: Decimal, currency: str = "GBP"
) -> RangeResult:
    """Builds a RangeResult directly from an already-produced best/likely/
    worst triple instead of deriving one from a formula (compute_range) —
    used only when a binding obligation has no expert CostTemplate to
    source a formula from and services/cost_estimate has asked an LLM for
    a company-specific estimate instead (CONVENTIONS.md rule 1's narrow
    cost-estimation exception).

    services/cost_estimate/schemas.py::CostEstimate already enforces
    best <= likely <= worst on whatever the model returned; this function
    re-checks it so no caller can construct a nonsensical RangeResult
    from this entry point, matching compute_range's own guarantee.
    """
    if not (best <= likely <= worst):
        raise ValueError(f"best ({best}) <= likely ({likely}) <= worst ({worst}) must hold")
    return RangeResult(best=best, likely=likely, worst=worst, currency=currency)


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
