"""Deterministic rationale assembly — CONVENTIONS.md rule #1: no AI at
analysis time. Every AnalysisItem's written explanation is built here,
purely from predicate metadata (the obligation summary, the expression's
own field-level conditions) and clause references — never composed by an
LLM at F4 runtime. "Does not bind" rationales get the same structured
treatment as "binds" ones (F4 success criterion: exclusions are half the
value, every row challengeable).
"""

from __future__ import annotations

from typing import Any

from engine.completeness.catalog import FIELD_BY_KEY
from engine.predicates.dsl import Expression, collect_leaves
from engine.predicates.evaluate import PredicateEvaluation, PredicateOutcome, evaluate_predicate


def _field_label(key: str) -> str:
    spec = FIELD_BY_KEY.get(key)
    return spec.label if spec else key


def _clause_citation(clause_refs: tuple[str, ...]) -> str:
    return f" ({', '.join(clause_refs)})" if clause_refs else ""


def _condition_lines(expression: Expression, facts: dict[str, Any]) -> list[str]:
    lines = []
    for leaf in collect_leaves(expression):
        label = _field_label(leaf["field"])
        leaf_outcome = evaluate_predicate(leaf, facts).outcome
        state = {
            PredicateOutcome.BINDS: "condition met",
            PredicateOutcome.DOES_NOT_BIND: "condition not met",
            PredicateOutcome.AMBIGUOUS: "not yet known",
        }[leaf_outcome]
        lines.append(f"{label}: {state}")
    return lines


def build_rationale(
    *,
    obligation_summary: str,
    expression: Expression,
    facts: dict[str, Any],
    evaluation: PredicateEvaluation,
    clause_refs: tuple[str, ...] = (),
) -> str:
    """One written rationale for a single AnalysisItem.

    `evaluation` is the already-computed top-level PredicateEvaluation
    (see engine/predicates.evaluate_predicate) — this function doesn't
    re-derive the outcome, only explains it, so the rationale can never
    disagree with the stored result.
    """
    citation = _clause_citation(clause_refs)
    conditions = "; ".join(_condition_lines(expression, facts)) or "no conditions"
    summary = obligation_summary.rstrip(".")

    if evaluation.outcome is PredicateOutcome.BINDS:
        return f"Binds: {summary}{citation}. Conditions — {conditions}."

    if evaluation.outcome is PredicateOutcome.DOES_NOT_BIND:
        return (
            f"Does not bind: {summary}{citation} was assessed against this profile and the "
            f"triggering condition isn't met. Conditions — {conditions}."
        )

    missing_labels = ", ".join(_field_label(key) for key in evaluation.missing_field_keys)
    return (
        f"Ambiguous: whether {summary}{citation} applies depends on information not yet in "
        f"the profile — {missing_labels}. Conditions — {conditions}."
    )
