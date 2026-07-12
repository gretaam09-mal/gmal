from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from engine.confidence.rubric import (
    MATURITY_TIER_SCORES,
    SCENARIO_SOURCE_SCORES,
    ConfidenceResult,
    compute_confidence_grade,
)

# --- Example-based: the rubric's grade bands are the spec, pin them exactly. ---


def test_perfect_inputs_grade_a():
    result = compute_confidence_grade(
        profile_completeness_score=1.0,
        template_maturity_tier="quoted",
        extraction_confidence_pct=100,
        scenario_source_quality="base_rate_table",
    )
    assert result.grade == "A"
    assert result.score == Decimal("100.0")


def test_weakest_inputs_grade_d():
    result = compute_confidence_grade(
        profile_completeness_score=0.0,
        template_maturity_tier="rough",
        extraction_confidence_pct=0,
        scenario_source_quality="unvalidated",
    )
    assert result.grade == "D"


def test_all_zero_factor_scores_grade_d_with_zero_score():
    result = compute_confidence_grade(
        profile_completeness_score=0.0,
        template_maturity_tier="not-a-real-tier",
        extraction_confidence_pct=0,
        scenario_source_quality="not-a-real-source",
    )
    assert result.grade == "D"
    assert result.score == Decimal("0.0")


def test_unknown_maturity_tier_scores_zero_rather_than_raising():
    result = compute_confidence_grade(
        profile_completeness_score=1.0,
        template_maturity_tier="not-a-real-tier",
        extraction_confidence_pct=100,
        scenario_source_quality="base_rate_table",
    )
    assert result.factor_scores["template_maturity"] == Decimal("0")


def test_settled_instruments_default_scenario_quality_to_not_applicable():
    result = compute_confidence_grade(
        profile_completeness_score=1.0,
        template_maturity_tier="quoted",
        extraction_confidence_pct=100,
    )
    assert (
        result.factor_scores["scenario_source_quality"]
        == SCENARIO_SOURCE_SCORES["not_applicable"]
    )


def test_result_reports_every_factor_score():
    result = compute_confidence_grade(
        profile_completeness_score=0.5,
        template_maturity_tier="benchmarked",
        extraction_confidence_pct=60,
        scenario_source_quality="expert_override",
    )
    assert set(result.factor_scores) == {
        "profile_completeness",
        "template_maturity",
        "extraction_confidence",
        "scenario_source_quality",
    }


# --- Property-based: invariants that must hold for any rubric inputs. ---

_completeness = st.floats(min_value=0, max_value=1, allow_nan=False)
_extraction_pct = st.floats(min_value=0, max_value=100, allow_nan=False)
_maturity_tiers = st.sampled_from(list(MATURITY_TIER_SCORES))
_scenario_qualities = st.sampled_from(list(SCENARIO_SOURCE_SCORES))


@given(
    completeness=_completeness,
    tier=_maturity_tiers,
    extraction=_extraction_pct,
    scenario=_scenario_qualities,
)
def test_grade_is_always_one_of_the_four_published_bands(completeness, tier, extraction, scenario):
    result = compute_confidence_grade(
        profile_completeness_score=completeness,
        template_maturity_tier=tier,
        extraction_confidence_pct=extraction,
        scenario_source_quality=scenario,
    )
    assert result.grade in ("A", "B", "C", "D")


@given(
    low=_completeness,
    high=_completeness,
    tier=_maturity_tiers,
    extraction=_extraction_pct,
    scenario=_scenario_qualities,
)
def test_higher_profile_completeness_never_lowers_the_score(low, high, tier, extraction, scenario):
    small, big = sorted((low, high))
    worse = compute_confidence_grade(
        profile_completeness_score=small,
        template_maturity_tier=tier,
        extraction_confidence_pct=extraction,
        scenario_source_quality=scenario,
    )
    better = compute_confidence_grade(
        profile_completeness_score=big,
        template_maturity_tier=tier,
        extraction_confidence_pct=extraction,
        scenario_source_quality=scenario,
    )
    assert better.score >= worse.score


@given(
    completeness=_completeness,
    tier=_maturity_tiers,
    extraction=_extraction_pct,
    scenario=_scenario_qualities,
)
def test_compute_confidence_grade_is_deterministic(completeness, tier, extraction, scenario):
    kwargs = dict(
        profile_completeness_score=completeness,
        template_maturity_tier=tier,
        extraction_confidence_pct=extraction,
        scenario_source_quality=scenario,
    )
    assert compute_confidence_grade(**kwargs) == compute_confidence_grade(**kwargs)
    assert isinstance(compute_confidence_grade(**kwargs), ConfidenceResult)
