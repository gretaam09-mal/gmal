"""Impact quantification: pure functions turning matched predicates into figures.

Pure and deterministic — see engine/__init__.py.
"""

from engine.impact.calculator import ImpactResult, compute_impact, impact_band
from engine.impact.phasing import PhaseEntry, phase_schedule
from engine.impact.present_value import discount_to_present_value
from engine.impact.range import RangeResult, compute_range, range_from_estimate
from engine.impact.scenarios import BASE_RATE_TABLES, ScenarioWeight, compute_weighted_range

__all__ = [
    "ImpactResult",
    "compute_impact",
    "impact_band",
    "PhaseEntry",
    "phase_schedule",
    "discount_to_present_value",
    "RangeResult",
    "compute_range",
    "range_from_estimate",
    "BASE_RATE_TABLES",
    "ScenarioWeight",
    "compute_weighted_range",
]
