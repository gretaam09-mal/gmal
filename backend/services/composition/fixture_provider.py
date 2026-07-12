"""A deterministic, offline stand-in for P-COMPOSE.

Used by tests and the golden-set runner — no test in this repo makes a
live model call, matching the fixture-testing pattern
services/companies_house established. A route only ever gets this via
explicit dependency injection, never as a silent fallback when a real
key is missing (see api/deps.py — the default provider is
AnthropicCompositionProvider, which fails closed).
"""
from __future__ import annotations

from services.composition.context import MemoComposeContext
from services.composition.provider import CompositionError
from services.composition.schemas import ComposedMemoProse
from services.composition.validator import validate_composed_memo


def _context_key(context: MemoComposeContext) -> str:
    return "|".join(obligation.predicate_id for obligation in context.binding_obligations)


class FixtureCompositionProvider:
    def __init__(self, fixtures: dict[str, ComposedMemoProse] | None = None) -> None:
        self._fixtures: dict[str, ComposedMemoProse] = dict(fixtures or {})

    def register(self, key: str, prose: ComposedMemoProse) -> None:
        self._fixtures[key] = prose

    def compose(self, context: MemoComposeContext) -> ComposedMemoProse:
        key = _context_key(context)
        try:
            prose = self._fixtures[key]
        except KeyError:
            raise CompositionError(
                f"No fixture registered for context {key!r} — "
                "FixtureCompositionProvider.register() it first"
            ) from None
        validate_composed_memo(prose, context)
        return prose
