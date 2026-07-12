import pytest
from pydantic import ValidationError

from services.extraction import ExtractedObligation


def _obligation(**overrides):
    base = dict(
        summary="A firm must appoint a compliance officer.",
        obligation_type="appointment",
        who={"value": "authorised firms", "clause_ref": "s.1", "confidence": 90},
        what={"value": "appoint a compliance officer", "clause_ref": "s.1", "confidence": 95},
        when={"value": "not specified in this clause", "clause_ref": "s.1", "confidence": 40},
        threshold={"value": "not specified in this clause", "clause_ref": "s.1", "confidence": 40},
        enforcer={"value": "the FCA", "clause_ref": "s.1", "confidence": 80},
        confidence=85,
    )
    base.update(overrides)
    return ExtractedObligation.model_validate(base)


def test_valid_obligation_round_trips():
    obligation = _obligation()
    assert obligation.summary.startswith("A firm must")
    assert obligation.who.clause_ref == "s.1"


def test_confidence_out_of_range_is_rejected():
    with pytest.raises(ValidationError):
        _obligation(confidence=101)
    with pytest.raises(ValidationError):
        _obligation(confidence=-1)


def test_missing_clause_ref_is_rejected():
    with pytest.raises(ValidationError):
        _obligation(who={"value": "authorised firms", "clause_ref": "", "confidence": 90})


def test_missing_field_is_rejected():
    data = _obligation().model_dump()
    del data["enforcer"]
    with pytest.raises(ValidationError):
        ExtractedObligation.model_validate(data)


def test_to_fields_json_has_all_five_slots_with_clause_refs():
    fields = _obligation().to_fields_json()
    assert set(fields) == {"who", "what", "when", "threshold", "enforcer"}
    for slot in fields.values():
        assert slot["clause_ref"]
        assert 0 <= slot["confidence"] <= 100


def test_clause_refs_deduplicates_and_sorts():
    # Defaults are all "s.1"; only `who` here points at a different clause.
    obligation = _obligation(who={"value": "x", "clause_ref": "s.2", "confidence": 90})
    assert obligation.clause_refs() == ("s.1", "s.2")
