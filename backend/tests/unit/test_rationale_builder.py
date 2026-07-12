from engine.predicates import PredicateEvaluation, PredicateOutcome, evaluate_predicate
from engine.rationale import build_rationale


def test_binds_rationale_cites_clause_and_summary():
    expr = {"field": "footprint.processes_personal_data", "equals": True}
    facts = {"footprint.processes_personal_data": True}
    evaluation = evaluate_predicate(expr, facts)

    text = build_rationale(
        obligation_summary="Appoint a data protection officer",
        expression=expr,
        facts=facts,
        evaluation=evaluation,
        clause_refs=("s.4(2)",),
    )
    assert text.startswith("Binds:")
    assert "Appoint a data protection officer" in text
    assert "s.4(2)" in text
    assert "Processes personal data at scale?: condition met" in text


def test_does_not_bind_rationale_is_first_class_not_an_afterthought():
    expr = {"field": "footprint.holds_client_money", "equals": True}
    facts = {"footprint.holds_client_money": False}
    evaluation = evaluate_predicate(expr, facts)

    text = build_rationale(
        obligation_summary="Segregate client money.",
        expression=expr,
        facts=facts,
        evaluation=evaluation,
        clause_refs=("CASS 7.1",),
    )
    assert text.startswith("Does not bind:")
    assert "Segregate client money" in text
    assert "CASS 7.1" in text
    assert "condition not met" in text


def test_ambiguous_rationale_names_the_missing_field():
    expr = {"field": "footprint.regulated_activity", "equals": True}
    facts = {}
    evaluation = evaluate_predicate(expr, facts)
    assert evaluation.outcome is PredicateOutcome.AMBIGUOUS

    text = build_rationale(
        obligation_summary="Hold FCA permissions.",
        expression=expr,
        facts=facts,
        evaluation=evaluation,
    )
    assert text.startswith("Ambiguous:")
    assert "Carries out an FCA/PRA-regulated activity?" in text


def test_rationale_never_disagrees_with_the_stored_evaluation():
    """The rationale explains the outcome it's handed — it must not
    re-derive a different one, even if given inconsistent evaluation."""
    expr = {"field": "x", "equals": True}
    facts = {"x": True}
    fabricated = PredicateEvaluation(outcome=PredicateOutcome.DOES_NOT_BIND)

    text = build_rationale(
        obligation_summary="Do the thing.", expression=expr, facts=facts, evaluation=fabricated
    )
    assert text.startswith("Does not bind:")
