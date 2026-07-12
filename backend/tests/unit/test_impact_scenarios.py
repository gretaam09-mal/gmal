from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from engine.impact.range import RangeResult
from engine.impact.scenarios import ScenarioWeight, compute_weighted_range

# --- Example-based: the weighting shape is the spec, pin it exactly. ---


def test_single_scenario_at_probability_one_is_unchanged():
    """A settled instrument uses a single as-drafted scenario at
    probability 1.0 — the weighted range must equal it exactly."""
    range_result = RangeResult(
        best=Decimal(100), likely=Decimal(200), worst=Decimal(300), currency="GBP"
    )
    weights = (ScenarioWeight(scenario="as_drafted", probability=Decimal("1"), range=range_result),)
    assert compute_weighted_range(weights) == range_result


def test_two_scenarios_weighted_evenly_average_the_ranges():
    a = RangeResult(best=Decimal(100), likely=Decimal(100), worst=Decimal(100), currency="GBP")
    b = RangeResult(best=Decimal(300), likely=Decimal(300), worst=Decimal(300), currency="GBP")
    weights = (
        ScenarioWeight(scenario="as_drafted", probability=Decimal("0.5"), range=a),
        ScenarioWeight(scenario="amended", probability=Decimal("0.5"), range=b),
    )
    result = compute_weighted_range(weights)
    assert result.best == Decimal(200)
    assert result.likely == Decimal(200)
    assert result.worst == Decimal(200)


def test_probabilities_are_normalised_when_they_do_not_sum_to_one():
    a = RangeResult(best=Decimal(100), likely=Decimal(100), worst=Decimal(100), currency="GBP")
    b = RangeResult(best=Decimal(300), likely=Decimal(300), worst=Decimal(300), currency="GBP")
    weights = (
        ScenarioWeight(scenario="as_drafted", probability=Decimal("1"), range=a),
        ScenarioWeight(scenario="amended", probability=Decimal("1"), range=b),
    )
    result = compute_weighted_range(weights)
    assert result.likely == Decimal(200)


def test_missing_scenario_requires_at_least_one_entry():
    import pytest

    with pytest.raises(ValueError):
        compute_weighted_range(())


# --- Property-based: invariants that must hold for any set of scenarios. ---

_probabilities = st.integers(min_value=1, max_value=100).map(lambda p: Decimal(p) / 100)
_amounts = st.integers(min_value=0, max_value=1_000_000).map(lambda cents: Decimal(cents) / 100)


@st.composite
def _scenario_weight(draw, name):
    probability = draw(_probabilities)
    best = draw(_amounts)
    likely = best + draw(_amounts)
    worst = likely + draw(_amounts)
    return ScenarioWeight(
        scenario=name,
        probability=probability,
        range=RangeResult(best=best, likely=likely, worst=worst, currency="GBP"),
    )


_three_scenarios = st.tuples(
    _scenario_weight("as_drafted"), _scenario_weight("amended"), _scenario_weight("delayed")
)


@given(weights=_three_scenarios)
def test_weighted_range_is_bounded_by_the_scenario_extremes(weights):
    result = compute_weighted_range(weights)
    bests = [w.range.best for w in weights]
    likelies = [w.range.likely for w in weights]
    worsts = [w.range.worst for w in weights]
    assert min(bests) <= result.best <= max(bests)
    assert min(likelies) <= result.likely <= max(likelies)
    assert min(worsts) <= result.worst <= max(worsts)


@given(weights=_three_scenarios)
def test_compute_weighted_range_is_deterministic(weights):
    assert compute_weighted_range(weights) == compute_weighted_range(weights)
