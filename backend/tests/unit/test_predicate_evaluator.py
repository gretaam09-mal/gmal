import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine.predicates import InvalidExpressionError, PredicateOutcome, evaluate_predicate
from engine.predicates.dsl import validate_expression

# --- Example-based: the tri-state truth table is the spec, pin it exactly. ---


def test_leaf_binds_when_fact_matches():
    expr = {"field": "footprint.processes_personal_data", "equals": True}
    result = evaluate_predicate(expr, {"footprint.processes_personal_data": True})
    assert result.outcome is PredicateOutcome.BINDS
    assert result.missing_field_keys == ()


def test_leaf_does_not_bind_when_fact_contradicts():
    expr = {"field": "footprint.processes_personal_data", "equals": True}
    result = evaluate_predicate(expr, {"footprint.processes_personal_data": False})
    assert result.outcome is PredicateOutcome.DOES_NOT_BIND


@pytest.mark.parametrize("facts", [{}, {"footprint.processes_personal_data": None}])
def test_leaf_is_ambiguous_when_fact_missing_or_unknown(facts):
    expr = {"field": "footprint.processes_personal_data", "equals": True}
    result = evaluate_predicate(expr, facts)
    assert result.outcome is PredicateOutcome.AMBIGUOUS
    assert result.missing_field_keys == ("footprint.processes_personal_data",)


def test_exists_leaf_is_never_ambiguous():
    expr = {"field": "footprint.processes_personal_data", "exists": True}
    assert evaluate_predicate(expr, {}).outcome is PredicateOutcome.DOES_NOT_BIND
    assert evaluate_predicate(expr, {"footprint.processes_personal_data": True}).outcome is (
        PredicateOutcome.BINDS
    )


def test_all_short_circuits_to_does_not_bind_even_with_unknown_sibling():
    """A definite False wins over ambiguity — "doesn't hold client money"
    rules FCA client-money rules out regardless of unanswered questions."""
    expr = {
        "all": [
            {"field": "footprint.holds_client_money", "equals": True},
            {"field": "scale.employee_count", "gte": 250},  # unanswered
        ]
    }
    facts = {"footprint.holds_client_money": False}
    result = evaluate_predicate(expr, facts)
    assert result.outcome is PredicateOutcome.DOES_NOT_BIND
    assert result.missing_field_keys == ()


def test_all_is_ambiguous_when_no_child_is_false_but_one_is_unknown():
    expr = {
        "all": [
            {"field": "footprint.holds_client_money", "equals": True},
            {"field": "scale.employee_count", "gte": 250},
        ]
    }
    facts = {"footprint.holds_client_money": True}
    result = evaluate_predicate(expr, facts)
    assert result.outcome is PredicateOutcome.AMBIGUOUS
    assert result.missing_field_keys == ("scale.employee_count",)


def test_all_binds_only_when_every_child_binds():
    expr = {
        "all": [
            {"field": "footprint.holds_client_money", "equals": True},
            {"field": "scale.employee_count", "gte": 250},
        ]
    }
    facts = {"footprint.holds_client_money": True, "scale.employee_count": 300}
    assert evaluate_predicate(expr, facts).outcome is PredicateOutcome.BINDS


def test_all_of_empty_list_is_vacuously_true():
    assert evaluate_predicate({"all": []}, {}).outcome is PredicateOutcome.BINDS


def test_any_short_circuits_to_binds_even_with_unknown_sibling():
    expr = {
        "any": [
            {"field": "footprint.has_overseas_operations", "equals": True},
            {"field": "footprint.processes_personal_data", "equals": True},  # unanswered
        ]
    }
    facts = {"footprint.has_overseas_operations": True}
    result = evaluate_predicate(expr, facts)
    assert result.outcome is PredicateOutcome.BINDS
    assert result.missing_field_keys == ()


def test_any_is_ambiguous_when_no_child_true_but_one_unknown():
    expr = {
        "any": [
            {"field": "footprint.has_overseas_operations", "equals": True},
            {"field": "footprint.processes_personal_data", "equals": True},
        ]
    }
    facts = {"footprint.has_overseas_operations": False}
    result = evaluate_predicate(expr, facts)
    assert result.outcome is PredicateOutcome.AMBIGUOUS
    assert result.missing_field_keys == ("footprint.processes_personal_data",)


def test_any_of_empty_list_is_false():
    assert evaluate_predicate({"any": []}, {}).outcome is PredicateOutcome.DOES_NOT_BIND


def test_not_inverts_true_and_false_but_preserves_ambiguity():
    field = {"field": "footprint.processes_personal_data", "equals": True}
    negated_true = evaluate_predicate({"not": field}, {"footprint.processes_personal_data": True})
    assert negated_true.outcome is PredicateOutcome.DOES_NOT_BIND

    negated_false = evaluate_predicate(
        {"not": field}, {"footprint.processes_personal_data": False}
    )
    assert negated_false.outcome is PredicateOutcome.BINDS

    ambiguous = evaluate_predicate({"not": field}, {})
    assert ambiguous.outcome is PredicateOutcome.AMBIGUOUS
    assert ambiguous.missing_field_keys == ("footprint.processes_personal_data",)


@pytest.mark.parametrize(
    ("op", "expected", "actual", "matches"),
    [
        ("equals", 5, 5, True),
        ("not_equals", 5, 6, True),
        ("gt", 5, 6, True),
        ("gte", 5, 5, True),
        ("lt", 5, 4, True),
        ("lte", 5, 5, True),
        ("in", [1, 2, 3], 2, True),
        ("not_in", [1, 2, 3], 9, True),
        ("contains", "64201", ["64201", "64202"], True),
    ],
)
def test_comparison_ops(op, expected, actual, matches):
    expr = {"field": "x", op: expected}
    result = evaluate_predicate(expr, {"x": actual})
    assert (result.outcome is PredicateOutcome.BINDS) is matches


def test_nested_combinators_compose():
    expr = {
        "all": [
            {"any": [{"field": "a", "equals": 1}, {"field": "b", "equals": 2}]},
            {"not": {"field": "c", "equals": 3}},
        ]
    }
    assert evaluate_predicate(expr, {"a": 1, "c": 4}).outcome is PredicateOutcome.BINDS
    assert evaluate_predicate(expr, {"a": 9, "c": 4}).outcome is PredicateOutcome.AMBIGUOUS
    assert evaluate_predicate(expr, {"a": 1, "c": 3}).outcome is PredicateOutcome.DOES_NOT_BIND


def test_evaluate_predicate_raises_on_malformed_expression():
    with pytest.raises(InvalidExpressionError):
        evaluate_predicate({"unknown": "shape"}, {})


@pytest.mark.parametrize(
    "bad",
    [
        {"all": "not-a-list"},
        {"field": "x"},  # no op
        {"field": "x", "gt": 1, "lt": 2},  # two ops
        {"field": "x", "weird_op": 1},
        {"field": 5, "equals": 1},
        "not-even-a-dict",
    ],
)
def test_validate_expression_rejects_malformed_shapes(bad):
    with pytest.raises(InvalidExpressionError):
        validate_expression(bad)


# --- Property-based: invariants that must hold for *any* expression tree. ---

_leaf_fields = st.sampled_from(["a", "b", "c"])
_leaf_values = st.one_of(st.booleans(), st.integers(min_value=0, max_value=10))


@st.composite
def _leaf(draw):
    field = draw(_leaf_fields)
    op = draw(st.sampled_from(["equals", "not_equals", "gt", "gte", "lt", "lte"]))
    value = draw(_leaf_values)
    return {"field": field, op: value}


def _expression(max_depth: int):
    leaf = _leaf()
    if max_depth <= 0:
        return leaf
    smaller = _expression(max_depth - 1)
    return st.one_of(
        leaf,
        st.lists(smaller, min_size=0, max_size=3).map(lambda kids: {"all": kids}),
        st.lists(smaller, min_size=0, max_size=3).map(lambda kids: {"any": kids}),
        smaller.map(lambda kid: {"not": kid}),
    )


_facts = st.dictionaries(
    st.sampled_from(["a", "b", "c"]),
    st.one_of(st.none(), st.booleans(), st.integers(min_value=0, max_value=10)),
)


@given(expr=_expression(max_depth=3), facts=_facts)
def test_double_negation_is_identity(expr, facts):
    validate_expression(expr)  # composite strategy always yields valid shapes
    direct = evaluate_predicate(expr, facts)
    double_negated = evaluate_predicate({"not": {"not": expr}}, facts)
    assert direct == double_negated


@given(expr=_expression(max_depth=3), facts=_facts)
def test_outcome_is_always_one_of_the_three_states_and_missing_fields_only_when_ambiguous(
    expr, facts
):
    result = evaluate_predicate(expr, facts)
    assert result.outcome in (
        PredicateOutcome.BINDS,
        PredicateOutcome.DOES_NOT_BIND,
        PredicateOutcome.AMBIGUOUS,
    )
    if result.outcome is not PredicateOutcome.AMBIGUOUS:
        assert result.missing_field_keys == ()


@given(expr=_expression(max_depth=3), facts=_facts)
def test_evaluation_is_deterministic(expr, facts):
    assert evaluate_predicate(expr, facts) == evaluate_predicate(expr, dict(facts))


@given(children=st.lists(_leaf(), min_size=1, max_size=4), facts=_facts)
def test_all_is_order_independent(children, facts):
    forward = evaluate_predicate({"all": children}, facts)
    backward = evaluate_predicate({"all": list(reversed(children))}, facts)
    assert forward == backward


@given(children=st.lists(_leaf(), min_size=1, max_size=4), facts=_facts)
def test_any_is_order_independent(children, facts):
    forward = evaluate_predicate({"any": children}, facts)
    backward = evaluate_predicate({"any": list(reversed(children))}, facts)
    assert forward == backward
