"""P-DIFF-NOTE: turns a structured engine/diff.Change tuple into a
one-paragraph change note — see ai/prompts/P-DIFF-NOTE.v1.md. Numbers
never come from the LLM; see validator.py for the post-render check.
"""

from services.diff_note.anthropic_provider import AnthropicDiffNoteProvider
from services.diff_note.fixture_provider import FixtureDiffNoteProvider
from services.diff_note.provider import DiffNoteError, DiffNoteProvider
from services.diff_note.schemas import ComposedDiffNote

__all__ = [
    "AnthropicDiffNoteProvider",
    "ComposedDiffNote",
    "DiffNoteError",
    "DiffNoteProvider",
    "FixtureDiffNoteProvider",
]
