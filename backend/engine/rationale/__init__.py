"""Deterministic rationale assembly for AnalysisItem results.

Pure and deterministic — see engine/__init__.py. No AI call ever happens
here; see engine/rationale/builder.py for why.
"""

from engine.rationale.builder import build_rationale

__all__ = ["build_rationale"]
