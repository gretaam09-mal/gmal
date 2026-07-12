from decimal import Decimal

import pytest
from pydantic import ValidationError

from services.composition.context import MemoComposeContext, ObligationComposeInput
from services.composition.provider import CompositionError
from services.composition.schemas import ComposedMemoProse
from services.composition.validator import (
    NumeralTraceabilityError,
    assert_numerals_trace_to_engine_output,
    extract_numerals,
    validate_composed_memo,
)

# --- Schema validation ---


def test_composed_memo_prose_validates_well_formed_input():
    prose = ComposedMemoProse.model_validate(
        {
            "headline_summary": "This deal carries a moderate regulatory exposure.",
            "obligations": [
                {
                    "predicate_id": "pred-1",
                    "what_it_requires": "Appoint a data protection officer.",
                    "why_it_applies": "The target processes personal data at scale.",
                }
            ],
            "excluded_summary": "No other obligations were excluded.",
        }
    )
    assert prose.obligations[0].predicate_id == "pred-1"


def test_composed_memo_prose_rejects_empty_headline():
    with pytest.raises(ValidationError):
        ComposedMemoProse.model_validate(
            {"headline_summary": "", "obligations": [], "excluded_summary": "none"}
        )


# --- Numeral extraction ---


def test_extract_numerals_finds_currency_and_percentages():
    text = "Best case £20,000.00, likely £25,000.00, worst £32,500.00, weighted at 60%."
    assert extract_numerals(text) == ["£20,000.00", "£25,000.00", "£32,500.00", "60%"]


def test_extract_numerals_ignores_clause_citations_and_years():
    text = "Under clause 3(2) of the 2027 Act, section 5 applies."
    assert extract_numerals(text) == []


# --- Traceability assertion ---


def test_numerals_matching_allowed_values_pass():
    allowed = frozenset({Decimal("25000.00"), Decimal("60")})
    assert_numerals_trace_to_engine_output("Likely cost is £25,000.00, weighted at 60%.", allowed)


def test_untraceable_numeral_raises():
    allowed = frozenset({Decimal("25000.00")})
    with pytest.raises(NumeralTraceabilityError):
        assert_numerals_trace_to_engine_output("The cost is actually £99,000.00.", allowed)


def test_validate_composed_memo_checks_every_prose_field():
    context = MemoComposeContext(
        headline_low=Decimal("20000"),
        headline_likely=Decimal("25000"),
        headline_high=Decimal("32500"),
        currency="GBP",
        confidence_grade="B",
        binding_obligations=(
            ObligationComposeInput(
                predicate_id="pred-1",
                obligation_summary="Appoint a DPO.",
                outcome="binds",
                rationale="Binds: processes personal data.",
                clause_texts=("A firm must appoint a DPO.",),
                clause_refs=("s.1",),
                impact_low=Decimal("20000"),
                impact_likely=Decimal("25000"),
                impact_high=Decimal("32500"),
                currency="GBP",
            ),
        ),
        excluded_obligations=(),
    )
    good_prose = ComposedMemoProse.model_validate(
        {
            "headline_summary": "Likely exposure is £25,000.00.",
            "obligations": [
                {
                    "predicate_id": "pred-1",
                    "what_it_requires": "Appoint a data protection officer.",
                    "why_it_applies": "Estimated cost is £25,000.00.",
                }
            ],
            "excluded_summary": "No exclusions.",
        }
    )
    validate_composed_memo(good_prose, context)  # does not raise

    bad_prose = ComposedMemoProse.model_validate(
        {
            "headline_summary": "Likely exposure is £99,000.00.",
            "obligations": good_prose.obligations,
            "excluded_summary": "No exclusions.",
        }
    )
    with pytest.raises(NumeralTraceabilityError):
        validate_composed_memo(bad_prose, context)


def test_allowed_numeral_values_collects_every_engine_figure():
    context = MemoComposeContext(
        headline_low=Decimal("1"),
        headline_likely=Decimal("2"),
        headline_high=Decimal("3"),
        currency="GBP",
        confidence_grade="A",
        binding_obligations=(
            ObligationComposeInput(
                predicate_id="p1",
                obligation_summary="s",
                outcome="binds",
                rationale="r",
                clause_texts=(),
                clause_refs=(),
                impact_low=Decimal("4"),
                impact_likely=Decimal("5"),
                impact_high=Decimal("6"),
                currency="GBP",
            ),
        ),
        excluded_obligations=(),
    )
    assert context.allowed_numeral_values() == frozenset(
        {Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5"), Decimal("6")}
    )


def test_composition_error_is_a_plain_exception():
    assert issubclass(CompositionError, Exception)
