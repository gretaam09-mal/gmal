from decimal import Decimal

from engine.impact.calculator import compute_impact, impact_band


def test_compute_impact_sums_base_and_terms():
    formula = {"base": 5000, "terms": [{"driver": "scale.employee_count", "rate": 40}]}
    result = compute_impact(formula, {"scale.employee_count": 100})
    assert result.amount == Decimal("5000") + Decimal("40") * Decimal("100")
    assert result.currency == "GBP"
    assert result.missing_driver_keys == ()


def test_compute_impact_sums_multiple_terms():
    formula = {
        "base": 1000,
        "terms": [
            {"driver": "scale.employee_count", "rate": 10},
            {"driver": "cost_sketch.compliance_headcount", "rate": 500},
        ],
    }
    result = compute_impact(
        formula, {"scale.employee_count": 50, "cost_sketch.compliance_headcount": 2}
    )
    assert result.amount == Decimal(1000) + Decimal(10) * 50 + Decimal(500) * 2


def test_compute_impact_is_unavailable_when_a_driver_is_missing():
    formula = {"base": 5000, "terms": [{"driver": "scale.employee_count", "rate": 40}]}
    result = compute_impact(formula, {})
    assert result.amount is None
    assert result.missing_driver_keys == ("scale.employee_count",)


def test_compute_impact_with_no_terms_is_just_the_base():
    result = compute_impact({"base": 2500}, {})
    assert result.amount == Decimal(2500)


def test_compute_impact_is_deterministic():
    formula = {"base": 100, "terms": [{"driver": "x", "rate": 3}]}
    facts = {"x": 7}
    assert compute_impact(formula, facts) == compute_impact(formula, dict(facts))


def test_impact_band_buckets():
    assert impact_band(None) == "Unknown"
    assert impact_band(Decimal(5_000)) == "< £10k"
    assert impact_band(Decimal(10_000)) == "£10k–£50k"
    assert impact_band(Decimal(49_999)) == "£10k–£50k"
    assert impact_band(Decimal(50_000)) == "£50k–£250k"
    assert impact_band(Decimal(249_999)) == "£50k–£250k"
    assert impact_band(Decimal(1_000_000)) == "£250k+"
