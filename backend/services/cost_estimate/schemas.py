"""Pydantic validation for P-COST-ESTIMATE's output — see
ai/prompts/P-COST-ESTIMATE.v1.md.

CONVENTIONS.md rule 1's narrow cost-estimation exception: this is the one
schema in the codebase where the LLM is *asked* to state numbers itself
(best/likely/worst GBP) rather than reuse ones it was given — there is no
expert CostTemplate to source a formula from, so the model has to produce
the estimate. Every other AI output here (ComposedMemoProse,
ComposedDiffNote) is the opposite: numbers must trace back to a given
figure, checked by a post-render validator. There is no equivalent
validator here because there is nothing to trace back to — the ordering
invariant below is the only structural guarantee this schema can offer.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class CostDriver(BaseModel):
    """One concrete driver of compliance cost the model identified —
    e.g. "external legal advice" or "compliance headcount" — with a
    short note on how it applies to this obligation."""

    driver: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=500)


class CostEstimate(BaseModel):
    """A company-specific best/likely/worst GBP estimate for one binding
    obligation, produced when no expert CostTemplate exists. Always
    labelled to the user as an AI-generated INDICATIVE estimate — see
    services/memo.py's cost_source field — and always superseded by an
    expert CostTemplate the moment one is attached."""

    cost_drivers: list[CostDriver] = Field(min_length=1)
    assumptions: list[str] = Field(min_length=1)
    best: Decimal = Field(ge=0)
    likely: Decimal = Field(ge=0)
    worst: Decimal = Field(ge=0)
    rationale: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def _range_is_ordered(self) -> CostEstimate:
        if not (self.best <= self.likely <= self.worst):
            raise ValueError(
                f"best ({self.best}) <= likely ({self.likely}) <= worst ({self.worst}) must hold"
            )
        return self
