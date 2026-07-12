from decimal import Decimal

import pytest
from pydantic import ValidationError

from engine.diff import Change, ChangeKind
from services.diff_note.provider import DiffNoteError
from services.diff_note.schemas import ComposedDiffNote
from services.diff_note.validator import assert_note_traces_to_diff, validate_diff_note

# --- Schema validation ---


def test_composed_diff_note_validates_well_formed_input():
    note = ComposedDiffNote.model_validate({"change_note": "The discount rate was raised."})
    assert note.change_note == "The discount rate was raised."


def test_composed_diff_note_rejects_empty_note():
    with pytest.raises(ValidationError):
        ComposedDiffNote.model_validate({"change_note": ""})


# --- Traceability against a structured diff ---


def _changes():
    return (
        Change(
            field="discount_rate_pct",
            kind=ChangeKind.CHANGED,
            before=Decimal("5"),
            after=Decimal("8"),
            delta=Decimal("3"),
        ),
    )


def test_note_referencing_diff_values_passes():
    note = "The discount rate moved from 5% to 8%, an increase of 3 percentage points."
    assert_note_traces_to_diff(note, _changes())


def test_note_with_untraceable_numeral_raises():
    note = "The discount rate moved to 99%."
    with pytest.raises(DiffNoteError):
        assert_note_traces_to_diff(note, _changes())


def test_validate_diff_note_checks_the_note_field():
    good = ComposedDiffNote.model_validate(
        {"change_note": "The discount rate moved from 5% to 8%."}
    )
    validate_diff_note(good, _changes())  # does not raise

    bad = ComposedDiffNote.model_validate({"change_note": "The discount rate is now 99%."})
    with pytest.raises(DiffNoteError):
        validate_diff_note(bad, _changes())


def test_diff_note_error_is_a_plain_exception():
    assert issubclass(DiffNoteError, Exception)
