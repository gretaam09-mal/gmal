"""A deterministic, offline stand-in for P-COST-ESTIMATE.

Used by tests and the golden-set runner — no test in this repo makes a
live model call, matching the fixture-testing pattern
services/companies_house established. A route only ever gets this via
explicit dependency injection, never as a silent fallback when a real
key is missing (see api/deps.py — the default provider is
AnthropicCostEstimateProvider, which fails closed).
"""

from __future__ import annotations

from services.cost_estimate.context import CostEstimateContext
from services.cost_estimate.provider import CostEstimateError
from services.cost_estimate.schemas import CostEstimate


class FixtureCostEstimateProvider:
    def __init__(self, fixtures: dict[str, CostEstimate] | None = None) -> None:
        self._fixtures: dict[str, CostEstimate] = dict(fixtures or {})

    def register(self, predicate_id: str, estimate: CostEstimate) -> None:
        self._fixtures[predicate_id] = estimate

    def estimate(self, context: CostEstimateContext) -> CostEstimate:
        try:
            return self._fixtures[context.predicate_id]
        except KeyError:
            raise CostEstimateError(
                f"No fixture registered for predicate {context.predicate_id!r} — "
                "FixtureCostEstimateProvider.register() it first"
            ) from None
