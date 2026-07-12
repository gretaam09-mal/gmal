"""The input Provision hands to P-COMPOSE: engine output plus approved
rationale metadata and clause texts — never anything the LLM must
compute itself. Built by services/memo.py from an Analysis's items.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ObligationComposeInput:
    predicate_id: str
    obligation_summary: str
    outcome: str
    rationale: str
    clause_texts: tuple[str, ...]
    clause_refs: tuple[str, ...]
    impact_low: Decimal | None
    impact_likely: Decimal | None
    impact_high: Decimal | None
    currency: str


@dataclass(frozen=True)
class MemoComposeContext:
    headline_low: Decimal
    headline_likely: Decimal
    headline_high: Decimal
    currency: str
    confidence_grade: str
    binding_obligations: tuple[ObligationComposeInput, ...]
    excluded_obligations: tuple[ObligationComposeInput, ...]

    def allowed_numeral_values(self) -> frozenset[Decimal]:
        """Every figure P-COMPOSE's prose is allowed to reuse — the
        post-render validator (validator.py) rejects anything else."""
        values = {self.headline_low, self.headline_likely, self.headline_high}
        for obligation in (*self.binding_obligations, *self.excluded_obligations):
            for value in (obligation.impact_low, obligation.impact_likely, obligation.impact_high):
                if value is not None:
                    values.add(value)
        return frozenset(values)
