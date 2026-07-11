"""The applicability engine's core: a pure, deterministic tri-state
evaluator over the DSL in engine/predicates/dsl.py.

CONVENTIONS.md rule #1: no I/O, no wall-clock reads, no network, no LLM
calls. Same expression + same facts, same result, every time — that's
what makes this property-testable (see tests/unit/test_predicate_
evaluator.py) and what F4's POST /analyses endpoint calls in a loop.

Three-valued (Kleene) logic is the whole trick: a fact that's missing
from `facts` (not present, or present as None — ProfileFieldSource.UNKNOWN
serialises to None) makes that leaf UNKNOWN rather than raising. AND/OR
short-circuit on a decisive child before ambiguity matters — e.g. "does
not hold client money" definitively rules out FCA client-money rules
even if three other footprint questions are still unanswered. Only when
no child is decisive does the whole node become AMBIGUOUS, naming every
field that would have resolved it.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

from engine.predicates.dsl import Expression, validate_expression


class PredicateOutcome(str, enum.Enum):
    BINDS = "binds"
    DOES_NOT_BIND = "does_not_bind"
    AMBIGUOUS = "ambiguous"


class _Tri(enum.Enum):
    """Internal three-valued result — mapped to PredicateOutcome only at
    the top of evaluate_predicate, never exposed."""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PredicateEvaluation:
    outcome: PredicateOutcome
    missing_field_keys: tuple[str, ...] = ()
    """Only non-empty when outcome is AMBIGUOUS — the profile field(s)
    that would resolve it, for the Exposure List's ambiguity deep-link."""


def evaluate_predicate(expression: Expression, facts: dict[str, Any]) -> PredicateEvaluation:
    """Evaluate one predicate's expression against a profile's facts.

    `facts` is a flat field_key -> value mapping (see engine/completeness/
    catalog.py for the known keys) — the caller (services/analyses.py)
    builds this from a workspace's current ProfileField rows.
    """
    validate_expression(expression)
    tri, missing = _evaluate(expression, facts)
    outcome = {
        _Tri.TRUE: PredicateOutcome.BINDS,
        _Tri.FALSE: PredicateOutcome.DOES_NOT_BIND,
        _Tri.UNKNOWN: PredicateOutcome.AMBIGUOUS,
    }[tri]
    return PredicateEvaluation(outcome=outcome, missing_field_keys=tuple(sorted(missing)))


def _evaluate(node: Expression, facts: dict[str, Any]) -> tuple[_Tri, frozenset[str]]:
    if "all" in node:
        return _evaluate_all(node["all"], facts)
    if "any" in node:
        return _evaluate_any(node["any"], facts)
    if "not" in node:
        return _evaluate_not(node["not"], facts)
    return _evaluate_leaf(node, facts)


def _evaluate_all(children: list[Expression], facts: dict[str, Any]) -> tuple[_Tri, frozenset[str]]:
    if not children:
        return _Tri.TRUE, frozenset()  # vacuous truth
    results = [_evaluate(child, facts) for child in children]
    if any(tri is _Tri.FALSE for tri, _ in results):
        return _Tri.FALSE, frozenset()
    unknown_missing = frozenset().union(*(m for tri, m in results if tri is _Tri.UNKNOWN))
    if unknown_missing:
        return _Tri.UNKNOWN, unknown_missing
    return _Tri.TRUE, frozenset()


def _evaluate_any(children: list[Expression], facts: dict[str, Any]) -> tuple[_Tri, frozenset[str]]:
    if not children:
        return _Tri.FALSE, frozenset()
    results = [_evaluate(child, facts) for child in children]
    if any(tri is _Tri.TRUE for tri, _ in results):
        return _Tri.TRUE, frozenset()
    unknown_missing = frozenset().union(*(m for tri, m in results if tri is _Tri.UNKNOWN))
    if unknown_missing:
        return _Tri.UNKNOWN, unknown_missing
    return _Tri.FALSE, frozenset()


def _evaluate_not(child: Expression, facts: dict[str, Any]) -> tuple[_Tri, frozenset[str]]:
    tri, missing = _evaluate(child, facts)
    inverted = {_Tri.TRUE: _Tri.FALSE, _Tri.FALSE: _Tri.TRUE, _Tri.UNKNOWN: _Tri.UNKNOWN}[tri]
    return inverted, missing


def _evaluate_leaf(node: Expression, facts: dict[str, Any]) -> tuple[_Tri, frozenset[str]]:
    field = node["field"]
    present = field in facts and facts[field] is not None
    actual = facts.get(field)

    if "exists" in node:
        return (_Tri.TRUE if present == bool(node["exists"]) else _Tri.FALSE), frozenset()

    if not present:
        return _Tri.UNKNOWN, frozenset({field})

    op, expected = next((k, v) for k, v in node.items() if k != "field")
    matched = _COMPARATORS[op](actual, expected)
    return (_Tri.TRUE if matched else _Tri.FALSE), frozenset()


_COMPARATORS = {
    "equals": lambda actual, expected: actual == expected,
    "not_equals": lambda actual, expected: actual != expected,
    "gt": lambda actual, expected: actual > expected,
    "gte": lambda actual, expected: actual >= expected,
    "lt": lambda actual, expected: actual < expected,
    "lte": lambda actual, expected: actual <= expected,
    "in": lambda actual, expected: actual in expected,
    "not_in": lambda actual, expected: actual not in expected,
    "contains": lambda actual, expected: expected in actual,
}
