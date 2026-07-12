"""Post-render numeral-traceability validation for P-DIFF-NOTE output —
see services/composition/validator.py for the identical rationale
(CONVENTIONS.md rule 1). The allowed values here are every numeric
before/after/delta in the structured diff (engine/diff.Change) the note
was generated from — never a number the note itself computed.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from services.diff_note.provider import DiffNoteError
from services.prose_numerals import extract_numerals, normalise_numeral

if TYPE_CHECKING:
    from engine.diff import Change
    from services.diff_note.schemas import ComposedDiffNote

__all__ = ["DiffNoteError", "assert_note_traces_to_diff", "validate_diff_note"]


def _allowed_values(changes: tuple[Change, ...]) -> frozenset[Decimal]:
    values: set[Decimal] = set()
    for change in changes:
        for candidate in (change.before, change.after, change.delta):
            if isinstance(candidate, Decimal):
                values.add(candidate)
    return frozenset(values)


def assert_note_traces_to_diff(text: str, changes: tuple[Change, ...]) -> None:
    allowed = _allowed_values(changes)
    for token in extract_numerals(text):
        value = normalise_numeral(token)
        if value is None:
            continue
        if value not in allowed:
            raise DiffNoteError(
                f"change note contains numeral {token!r} that doesn't trace to "
                "the diff it was given"
            )


def validate_diff_note(note: ComposedDiffNote, changes: tuple[Change, ...]) -> None:
    assert_note_traces_to_diff(note.change_note, changes)
