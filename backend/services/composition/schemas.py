"""Pydantic validation for P-COMPOSE's output — see ai/prompts/P-COMPOSE.v1.md.

CONVENTIONS.md rule 1: the LLM never computes a number. It is given
engine-computed figures pre-formatted as strings in the prompt and told
to reuse them verbatim; services/composition/validator.py is the
post-render backstop that rejects any numeral in the output that doesn't
trace back to one of those figures.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ComposedObligationProse(BaseModel):
    """Memo-styled prose for one binding obligation — the "what it
    requires" / "why it applies" narrative around a cost range and
    timing the caller already has from engine/impact, not from this."""

    predicate_id: str = Field(min_length=1)
    what_it_requires: str = Field(min_length=1, max_length=800)
    why_it_applies: str = Field(min_length=1, max_length=800)


class ComposedMemoProse(BaseModel):
    """The full structured output of one P-COMPOSE call — narrative only.
    Every numeric figure in the memo (headline range, waterfall, per-
    obligation cost range, timing, confidence grade) is assembled
    separately in services/memo.py directly from engine output; this is
    only ever the prose wrapped around it."""

    headline_summary: str = Field(min_length=1, max_length=1500)
    obligations: list[ComposedObligationProse]
    excluded_summary: str = Field(min_length=1, max_length=1500)
