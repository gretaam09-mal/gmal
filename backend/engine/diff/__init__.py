"""Diffing: pure functions comparing two exposure computations or memo versions.

Pure and deterministic — see engine/__init__.py.
"""

from engine.diff.assumptions import compute_assumption_diff
from engine.diff.base import Change, ChangeKind

__all__ = ["Change", "ChangeKind", "compute_assumption_diff"]
