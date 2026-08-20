from decimal import Decimal

import pytest
from pydantic import ValidationError

from services.cost_estimate.context import CostEstimateContext, ProfileFact
from services.cost_estimate.fixture_provider import FixtureCostEstimateProvider
from services.cost_estimate.provider import CostEstimateError
from services.cost_estimate.schemas import CostEstimate

# --- Schema validation ---


def _valid_estimate_payload(**overrides) -> dict:
    payload = {
        "cost_drivers": [
            {"driver": "External legal advice", "detail": "Drafting a DPO appointment letter."},
        ],
        "assumptions": ["Assumes no existing DPO in post."],
        "best": "15000",
        "likely": "25000",
        "worst": "40000",
        "rationale": "Scaled headcount-based staffing driver to 500 employees.",
    }
    payload.update(overrides)
    return payload


def test_cost_estimate_validates_well_formed_input():
    estimate = CostEstimate.model_validate(_valid_estimate_payload())
    assert estimate.best == Decimal("15000")
    assert estimate.likely == Decimal("25000")
    assert estimate.worst == Decimal("40000")


def test_cost_estimate_rejects_out_of_order_range():
    with pytest.raises(ValidationError, match="must hold"):
        CostEstimate.model_validate(_valid_estimate_payload(best="40000", worst="15000"))


def test_cost_estimate_rejects_empty_cost_drivers():
    with pytest.raises(ValidationError):
        CostEstimate.model_validate(_valid_estimate_payload(cost_drivers=[]))


def test_cost_estimate_rejects_empty_assumptions():
    with pytest.raises(ValidationError):
        CostEstimate.model_validate(_valid_estimate_payload(assumptions=[]))


def test_cost_estimate_rejects_negative_figures():
    with pytest.raises(ValidationError):
        CostEstimate.model_validate(_valid_estimate_payload(best="-1"))


# --- Fixture provider ---


def _context(predicate_id: str = "pred-1") -> CostEstimateContext:
    return CostEstimateContext(
        predicate_id=predicate_id,
        obligation_summary="Appoint a data protection officer.",
        rationale="Binds: processes personal data at scale.",
        clause_refs=("s.1",),
        clause_texts=("A firm must appoint a DPO.",),
        company_facts=(ProfileFact(label="Employee count", value="500"),),
    )


def test_fixture_provider_returns_the_registered_estimate():
    provider = FixtureCostEstimateProvider()
    estimate = CostEstimate.model_validate(_valid_estimate_payload())
    provider.register("pred-1", estimate)

    result = provider.estimate(_context("pred-1"))

    assert result == estimate


def test_fixture_provider_raises_a_clear_error_when_unregistered():
    provider = FixtureCostEstimateProvider()
    with pytest.raises(CostEstimateError, match="pred-1"):
        provider.estimate(_context("pred-1"))


def test_cost_estimate_error_is_a_plain_exception():
    assert issubclass(CostEstimateError, Exception)
