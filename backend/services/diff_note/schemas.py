"""Pydantic validation for P-DIFF-NOTE's output — see
ai/prompts/P-DIFF-NOTE.v1.md.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ComposedDiffNote(BaseModel):
    """One paragraph explaining what changed and why — the numbers it
    may reference come entirely from the engine/diff.Change entries it
    was given; see services/diff_note/validator.py."""

    change_note: str = Field(min_length=1, max_length=1000)
