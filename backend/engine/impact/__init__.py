"""Impact quantification: pure functions turning matched predicates into figures.

Pure and deterministic — see engine/__init__.py.
"""

from engine.impact.calculator import ImpactResult, compute_impact, impact_band

__all__ = ["ImpactResult", "compute_impact", "impact_band"]
