from typing import Protocol

from services.cost_estimate.context import CostEstimateContext
from services.cost_estimate.schemas import CostEstimate


class CostEstimateError(Exception):
    """Raised when a provider can't produce a validated CostEstimate — a
    malformed LLM response, a missing fixture, or a misconfigured key.
    Cost estimation fails closed: a route never falls back to inventing
    a figure itself or silently omitting the obligation's cost."""


class CostEstimateProvider(Protocol):
    """P-COST-ESTIMATE's interface — see
    ai/prompts/P-COST-ESTIMATE.v1.md for the system rule this
    implements, and services/cost_estimate/fixture_provider.py /
    anthropic_provider.py for the two implementations."""

    def estimate(self, context: CostEstimateContext) -> CostEstimate: ...
