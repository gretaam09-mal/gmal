"""The predicate rule language: a small, JSON-serialisable expression tree.

Stored verbatim in Predicate.expression (see db/models/regulatory.py) —
never code, never something an LLM writes at analysis time (P-PREDICATE-
ASSIST only drafts one for a human to approve). Two node shapes:

Combinators — nest arbitrarily:
    {"all": [<node>, ...]}   AND
    {"any": [<node>, ...]}   OR
    {"not": <node>}          NOT

Leaves — test one profile fact:
    {"field": "footprint.processes_personal_data", "equals": True}
    {"field": "scale.employee_count", "gte": 250}
    {"field": "activity.sic_codes", "contains": "64201"}
    {"field": "footprint.holds_client_money", "exists": True}

Supported comparison ops: equals, not_equals, gt, gte, lt, lte, in,
not_in, contains. `exists` is special — see evaluate_leaf below.
"""

from __future__ import annotations

from typing import Any

Expression = dict[str, Any]

_COMPARISON_OPS = frozenset(
    {"equals", "not_equals", "gt", "gte", "lt", "lte", "in", "not_in", "contains"}
)


class InvalidExpressionError(ValueError):
    """Raised when a Predicate.expression doesn't match the DSL grammar —
    surfaced to the admin predicate editor as a validation error, never
    silently swallowed."""


def validate_expression(node: Expression) -> None:
    """Raises InvalidExpressionError if `node` isn't a well-formed
    expression tree. Called before a predicate is saved as DRAFT or
    APPROVED, and by the test-runner before evaluating it."""
    if not isinstance(node, dict):
        raise InvalidExpressionError(f"expression node must be an object, got {type(node)!r}")

    if "all" in node or "any" in node:
        key = "all" if "all" in node else "any"
        children = node[key]
        if not isinstance(children, list):
            raise InvalidExpressionError(f"'{key}' must be a list of nodes")
        for child in children:
            validate_expression(child)
        return

    if "not" in node:
        validate_expression(node["not"])
        return

    if "field" in node:
        field = node["field"]
        if not isinstance(field, str) or not field:
            raise InvalidExpressionError("leaf 'field' must be a non-empty string")
        ops = [k for k in node if k != "field"]
        if len(ops) != 1:
            raise InvalidExpressionError(
                f"leaf for field {field!r} must have exactly one op, got {ops}"
            )
        op = ops[0]
        if op != "exists" and op not in _COMPARISON_OPS:
            raise InvalidExpressionError(f"unknown op {op!r} for field {field!r}")
        return

    raise InvalidExpressionError(f"node {node!r} is not all/any/not or a field leaf")


def collect_leaves(node: Expression) -> list[Expression]:
    """Flatten an expression tree into its individual field-testing leaves,
    in left-to-right order. Used by engine/rationale to explain a result
    condition-by-condition rather than just as one pass/fail sentence."""
    if "all" in node:
        return [leaf for child in node["all"] for leaf in collect_leaves(child)]
    if "any" in node:
        return [leaf for child in node["any"] for leaf in collect_leaves(child)]
    if "not" in node:
        return collect_leaves(node["not"])
    return [node]
