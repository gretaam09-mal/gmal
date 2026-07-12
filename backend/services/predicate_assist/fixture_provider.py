"""A deterministic, offline stand-in for P-PREDICATE-ASSIST — same
rationale as services/extraction/fixture_provider.py: no test or sample-
data script in this repo makes a live model call.
"""

from __future__ import annotations

from typing import Any

from services.predicate_assist.provider import PredicateAssistError
from services.predicate_assist.schemas import DraftedPredicate


class FixturePredicateAssistProvider:
    def __init__(self, fixtures: dict[str, DraftedPredicate] | None = None) -> None:
        self._fixtures: dict[str, DraftedPredicate] = dict(fixtures or {})

    def register(self, obligation_summary: str, drafted: DraftedPredicate) -> None:
        self._fixtures[obligation_summary] = drafted

    def draft(
        self,
        *,
        obligation_summary: str,
        who_value: str,
        who_clause_ref: str,
        threshold_value: str,
        threshold_clause_ref: str,
        available_fields: list[dict[str, Any]],
    ) -> DraftedPredicate:
        del who_value, who_clause_ref, threshold_value, threshold_clause_ref, available_fields
        try:
            return self._fixtures[obligation_summary]
        except KeyError:
            raise PredicateAssistError(
                f"No fixture registered for obligation {obligation_summary!r}"
            ) from None
