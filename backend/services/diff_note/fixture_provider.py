"""A deterministic, offline stand-in for P-DIFF-NOTE — see
services/composition/fixture_provider.py for the pattern this follows.
"""
from __future__ import annotations

from engine.diff import Change
from services.diff_note.provider import DiffNoteError
from services.diff_note.schemas import ComposedDiffNote
from services.diff_note.validator import validate_diff_note


def _changes_key(changes: tuple[Change, ...]) -> str:
    return "|".join(sorted(change.field for change in changes))


class FixtureDiffNoteProvider:
    def __init__(self, fixtures: dict[str, ComposedDiffNote] | None = None) -> None:
        self._fixtures: dict[str, ComposedDiffNote] = dict(fixtures or {})

    def register(self, key: str, note: ComposedDiffNote) -> None:
        self._fixtures[key] = note

    def summarise(self, changes: tuple[Change, ...]) -> ComposedDiffNote:
        key = _changes_key(changes)
        try:
            note = self._fixtures[key]
        except KeyError:
            raise DiffNoteError(
                f"No fixture registered for changes {key!r} — "
                "FixtureDiffNoteProvider.register() it first"
            ) from None
        validate_diff_note(note, changes)
        return note
