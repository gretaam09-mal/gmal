"""Outcome-weighting for in-flight instruments — pure, no I/O.

A settled instrument always evaluates as a single as-drafted scenario at
probability 1.0 (see Instrument.in_flight). An in-flight one is weighted
across as-drafted/amended/delayed scenarios using expert-set
probabilities — this module only does the (pure) weighted-average maths;
the probabilities themselves are recorded, timestamped, and audited via
an append-only forecast_log entry (see services/scenarios.py), never
computed here. BASE_RATE_TABLES is the published, versioned starting
point an expert overrides rather than invents from scratch — see
engine/__init__.py: deterministic, no LLM arithmetic.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from engine.impact.range import RangeResult

# Documented base-rate table: a default probability split by scenario,
# used as the starting point for an expert's judgement call, never as a
# substitute for it. Keyed by instrument stage — "default" applies when a
# more specific stage isn't recorded.
BASE_RATE_TABLES: dict[str, dict[str, Decimal]] = {
    "default": {
        "as_drafted": Decimal("0.6"),
        "amended": Decimal("0.3"),
        "delayed": Decimal("0.1"),
    },
    "consultation": {
        "as_drafted": Decimal("0.4"),
        "amended": Decimal("0.45"),
        "delayed": Decimal("0.15"),
    },
    "draft_bill": {
        "as_drafted": Decimal("0.55"),
        "amended": Decimal("0.3"),
        "delayed": Decimal("0.15"),
    },
}


@dataclass(frozen=True)
class ScenarioWeight:
    scenario: str
    probability: Decimal
    range: RangeResult


def compute_weighted_range(weights: tuple[ScenarioWeight, ...]) -> RangeResult:
    if not weights:
        raise ValueError("at least one scenario is required")
    total_probability = sum((weight.probability for weight in weights), Decimal("0"))
    if total_probability <= 0:
        raise ValueError("scenario probabilities must sum to a positive value")

    def _weighted(attribute: str) -> Decimal | None:
        values = [getattr(weight.range, attribute) for weight in weights]
        if any(value is None for value in values):
            return None
        weighted_sum = sum(
            (getattr(weight.range, attribute) * weight.probability for weight in weights),
            Decimal("0"),
        )
        return weighted_sum / total_probability

    return RangeResult(
        best=_weighted("best"),
        likely=_weighted("likely"),
        worst=_weighted("worst"),
        currency=weights[0].range.currency,
    )
