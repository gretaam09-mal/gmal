from typing import Any, Protocol

from services.predicate_assist.schemas import DraftedPredicate


class PredicateAssistError(Exception):
    """Raised when a provider can't produce a validated DraftedPredicate."""


class PredicateAssistProvider(Protocol):
    """P-PREDICATE-ASSIST's interface. Every implementation only *drafts*
    — see ai/prompts/P-PREDICATE-ASSIST.v1.md and
    db/models/regulatory.py::Predicate for why nothing here can approve
    a predicate itself."""

    def draft(
        self,
        *,
        obligation_summary: str,
        who_value: str,
        who_clause_ref: str,
        threshold_value: str,
        threshold_clause_ref: str,
        available_fields: list[dict[str, Any]],
    ) -> DraftedPredicate: ...
