"""Predicate evaluation: pure functions mapping deal facts to applicable rules.

Pure and deterministic — see engine/__init__.py. `evaluate_predicate` is
the F4 applicability engine's core; `dsl` defines and validates the rule
language a Predicate.expression must satisfy.
"""

from engine.predicates.dsl import (
    Expression,
    InvalidExpressionError,
    collect_leaves,
    validate_expression,
)
from engine.predicates.evaluate import PredicateEvaluation, PredicateOutcome, evaluate_predicate

__all__ = [
    "Expression",
    "InvalidExpressionError",
    "PredicateEvaluation",
    "PredicateOutcome",
    "collect_leaves",
    "evaluate_predicate",
    "validate_expression",
]
