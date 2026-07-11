import pytest

from services.extraction import ExtractedObligation, ExtractionError, FixtureExtractionProvider

_OBLIGATION = ExtractedObligation.model_validate(
    {
        "summary": "A firm must appoint a compliance officer.",
        "obligation_type": "appointment",
        "who": {"value": "authorised firms", "clause_ref": "s.1", "confidence": 90},
        "what": {"value": "appoint a compliance officer", "clause_ref": "s.1", "confidence": 95},
        "when": {"value": "not specified in this clause", "clause_ref": "s.1", "confidence": 40},
        "threshold": {"value": "not specified", "clause_ref": "s.1", "confidence": 40},
        "enforcer": {"value": "the FCA", "clause_ref": "s.1", "confidence": 80},
        "confidence": 85,
    }
)


def test_registered_fixture_is_returned_deterministically():
    provider = FixtureExtractionProvider()
    provider.register("s.1", _OBLIGATION)

    first = provider.extract(clause_text="anything", clause_ref="s.1", instrument_title="Test Act")
    second = provider.extract(
        clause_text="anything else", clause_ref="s.1", instrument_title="Test Act"
    )
    assert first == second == _OBLIGATION


def test_unregistered_clause_raises_extraction_error():
    provider = FixtureExtractionProvider()
    with pytest.raises(ExtractionError):
        provider.extract(clause_text="x", clause_ref="s.99", instrument_title="Test Act")


def test_constructor_accepts_prebuilt_fixture_map():
    provider = FixtureExtractionProvider({"s.1": _OBLIGATION})
    result = provider.extract(clause_text="x", clause_ref="s.1", instrument_title="Test Act")
    assert result == _OBLIGATION
