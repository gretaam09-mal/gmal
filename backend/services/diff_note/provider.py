from typing import Protocol

from engine.diff import Change
from services.diff_note.schemas import ComposedDiffNote


class DiffNoteError(Exception):
    """Raised when a provider can't produce a validated, numeral-
    traceable ComposedDiffNote — a malformed LLM response, a missing
    fixture, a misconfigured key, or a note containing an untraceable
    numeral. Fails closed, same as CompositionError."""


class DiffNoteProvider(Protocol):
    """P-DIFF-NOTE's interface — see ai/prompts/P-DIFF-NOTE.v1.md."""

    def summarise(self, changes: tuple[Change, ...]) -> ComposedDiffNote: ...
