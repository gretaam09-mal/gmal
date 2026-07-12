"""Confidence grading: an A-D letter grade from a published rubric — pure, no I/O.

See engine/__init__.py: deterministic, no LLM arithmetic — this never lets
an AI system choose its own grade; P-COMPOSE only ever interpolates the
`grade` this produces.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

# Published rubric: each factor's weight in the overall confidence score.
FACTOR_WEIGHTS: dict[str, Decimal] = {
    "profile_completeness": Decimal("0.35"),
    "template_maturity": Decimal("0.25"),
    "extraction_confidence": Decimal("0.25"),
    "scenario_source_quality": Decimal("0.15"),
}

# template_maturity_tier and scenario_source_quality are categorical
# judgements recorded by staff (CostTemplate.maturity_tier, a scenario's
# recorded source) rather than measurements, so the rubric maps each
# vocabulary term to a fixed score instead of accepting an arbitrary float.
MATURITY_TIER_SCORES: dict[str, Decimal] = {
    "quoted": Decimal("1.0"),
    "benchmarked": Decimal("0.75"),
    "estimated": Decimal("0.5"),
    "rough": Decimal("0.25"),
}

SCENARIO_SOURCE_SCORES: dict[str, Decimal] = {
    "base_rate_table": Decimal("1.0"),
    "expert_override": Decimal("0.85"),
    "analogous_instrument": Decimal("0.6"),
    "unvalidated": Decimal("0.3"),
    # A settled (non-in_flight) instrument has no scenario judgement to
    # make at all — full credit, not a penalty for an inapplicable factor.
    "not_applicable": Decimal("1.0"),
}

# Grade bands: the minimum overall score (0-100) required for each grade,
# checked highest-first.
_GRADE_BANDS: tuple[tuple[Decimal, str], ...] = (
    (Decimal("85"), "A"),
    (Decimal("70"), "B"),
    (Decimal("50"), "C"),
    (Decimal("0"), "D"),
)


@dataclass(frozen=True)
class ConfidenceResult:
    grade: str
    score: Decimal
    factor_scores: dict[str, Decimal] = field(default_factory=dict)


def _clamp_unit(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("1"), value))


def compute_confidence_grade(
    *,
    profile_completeness_score: float,
    template_maturity_tier: str,
    extraction_confidence_pct: float,
    scenario_source_quality: str = "not_applicable",
) -> ConfidenceResult:
    factor_scores = {
        "profile_completeness": _clamp_unit(Decimal(str(profile_completeness_score))),
        "template_maturity": MATURITY_TIER_SCORES.get(template_maturity_tier, Decimal("0")),
        "extraction_confidence": _clamp_unit(
            Decimal(str(extraction_confidence_pct)) / Decimal("100")
        ),
        "scenario_source_quality": SCENARIO_SOURCE_SCORES.get(
            scenario_source_quality, Decimal("0")
        ),
    }
    weighted = sum(
        (factor_scores[name] * weight for name, weight in FACTOR_WEIGHTS.items()), Decimal("0")
    )
    score = (weighted * Decimal("100")).quantize(Decimal("0.1"))
    grade = next(letter for threshold, letter in _GRADE_BANDS if score >= threshold)
    return ConfidenceResult(grade=grade, score=score, factor_scores=factor_scores)
