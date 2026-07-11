import pytest
from pydantic import ValidationError

from services.predicate_assist import DraftedPredicate, FixturePredicateAssistProvider
from services.predicate_assist.provider import PredicateAssistError


def test_drafted_predicate_validates_expression_dsl():
    drafted = DraftedPredicate.model_validate(
        {
            "predicate_key": "processes_personal_data",
            "expression": {"field": "footprint.processes_personal_data", "equals": True},
            "explanation": "The obligation applies to firms that process personal data.",
        }
    )
    assert drafted.predicate_key == "processes_personal_data"


def test_drafted_predicate_rejects_malformed_expression():
    with pytest.raises(ValidationError):
        DraftedPredicate.model_validate(
            {
                "predicate_key": "bad",
                "expression": {"not_a_valid_shape": True},
                "explanation": "x",
            }
        )


def test_fixture_provider_is_deterministic_and_never_auto_approves():
    provider = FixturePredicateAssistProvider()
    drafted = DraftedPredicate.model_validate(
        {
            "predicate_key": "holds_client_money",
            "expression": {"field": "footprint.holds_client_money", "equals": True},
            "explanation": "Applies to firms holding client money.",
        }
    )
    provider.register("Segregate client money.", drafted)

    result = provider.draft(
        obligation_summary="Segregate client money.",
        who_value="firms holding client money",
        who_clause_ref="CASS 7.1",
        threshold_value="not specified",
        threshold_clause_ref="CASS 7.1",
        available_fields=[],
    )
    assert result == drafted
    # Nothing about draft() ever sets or implies an approved status —
    # that's a Predicate row concern, not the assist provider's.
    assert not hasattr(result, "status")


def test_fixture_provider_raises_for_unregistered_obligation():
    provider = FixturePredicateAssistProvider()
    with pytest.raises(PredicateAssistError):
        provider.draft(
            obligation_summary="unregistered",
            who_value="x",
            who_clause_ref="s.1",
            threshold_value="x",
            threshold_clause_ref="s.1",
            available_fields=[],
        )
