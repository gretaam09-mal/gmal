from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from engine.impact.range import RangeResult, compute_range

# --- Example-based: the range shape is the spec, pin it exactly. ---


def test_compute_range_applies_default_multipliers_to_the_likely_point():
    formula = {"base": 1000, "terms": [{"driver": "scale.employee_count", "rate": 10}]}
    result = compute_range(formula, {"scale.employee_count": 100})
    assert result.likely == Decimal(2000)
    assert result.best == Decimal(2000) * Decimal("0.8")
    assert result.worst == Decimal(2000) * Decimal("1.3")
    assert result.currency == "GBP"


def test_compute_range_honours_formula_declared_multipliers():
    formula = {
        "base": 1000,
        "terms": [],
        "range": {"low_multiplier": 0.5, "high_multiplier": 2.0},
    }
    result = compute_range(formula, {})
    assert result.best == Decimal(1000) * Decimal("0.5")
    assert result.worst == Decimal(1000) * Decimal("2.0")


def test_compute_range_is_unavailable_when_a_driver_is_missing():
    formula = {"base": 1000, "terms": [{"driver": "scale.employee_count", "rate": 10}]}
    result = compute_range(formula, {})
    assert result == RangeResult(
        best=None,
        likely=None,
        worst=None,
        currency="GBP",
        missing_driver_keys=("scale.employee_count",),
    )


# --- Property-based: invariants that must hold for any formula/facts. ---

_rates = st.integers(min_value=0, max_value=1000)
_bases = st.integers(min_value=0, max_value=100_000)
_driver_values = st.integers(min_value=0, max_value=10_000)


@given(base=_bases, rate=_rates, low=_driver_values, high=_driver_values)
def test_larger_driver_value_never_lowers_the_range(base, rate, low, high):
    """Monotonicity: a larger headcount (or any driver with a non-negative
    rate) never lowers a staffing-driven cost — best/likely/worst can only
    stay the same or increase."""
    small, big = sorted((low, high))
    formula = {"base": base, "terms": [{"driver": "scale.employee_count", "rate": rate}]}
    result_small = compute_range(formula, {"scale.employee_count": small})
    result_big = compute_range(formula, {"scale.employee_count": big})
    assert result_big.best >= result_small.best
    assert result_big.likely >= result_small.likely
    assert result_big.worst >= result_small.worst


@given(base=_bases, rate=_rates, driver=_driver_values)
def test_best_likely_worst_are_ordered(base, rate, driver):
    formula = {"base": base, "terms": [{"driver": "x", "rate": rate}]}
    result = compute_range(formula, {"x": driver})
    assert result.best <= result.likely <= result.worst


@given(base=_bases, rate=_rates, driver=_driver_values)
def test_compute_range_is_deterministic(base, rate, driver):
    formula = {"base": base, "terms": [{"driver": "x", "rate": rate}]}
    facts = {"x": driver}
    assert compute_range(formula, facts) == compute_range(formula, dict(facts))
