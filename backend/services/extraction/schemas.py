"""Pydantic validation for P-EXTRACT's output — see ai/prompts/P-EXTRACT.v1.md.

The system rule is enforced here, not just in the prompt: every field
must cite the clause it came from, and confidence is always 0-100. An
LLM response that doesn't match this shape is a validation error, not a
best-effort obligation — CONVENTIONS.md rule 1 means nothing here ever
carries a computed number, only extracted facts and citations.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExtractedField(BaseModel):
    """One who/what/when/threshold/enforcer slot: the extracted text plus
    the exact clause it was read from and how confident the extraction is
    about this one field specifically."""

    value: str = Field(min_length=1)
    clause_ref: str = Field(min_length=1)
    confidence: int = Field(ge=0, le=100)


class ExtractedObligation(BaseModel):
    """The full structured output of one P-EXTRACT call over one clause."""

    summary: str = Field(min_length=1, max_length=500)
    obligation_type: str = Field(min_length=1, max_length=100)
    who: ExtractedField
    what: ExtractedField
    when: ExtractedField
    threshold: ExtractedField
    enforcer: ExtractedField
    confidence: int = Field(ge=0, le=100)
    """Overall confidence in the obligation as a whole — separate from
    each field's own confidence, since e.g. `who` might be crystal clear
    while `threshold` is a stretch."""

    def to_fields_json(self) -> dict[str, Any]:
        """The shape stored in Obligation.fields (db/models/regulatory.py)."""
        return {
            "who": self.who.model_dump(),
            "what": self.what.model_dump(),
            "when": self.when.model_dump(),
            "threshold": self.threshold.model_dump(),
            "enforcer": self.enforcer.model_dump(),
        }

    def clause_refs(self) -> tuple[str, ...]:
        """Every distinct clause this obligation cites, for the analysis
        rationale (engine/rationale) and the review UI's side-by-side view."""
        slots = (self.who, self.what, self.when, self.threshold, self.enforcer)
        refs = {field.clause_ref for field in slots}
        return tuple(sorted(refs))
