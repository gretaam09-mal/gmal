import uuid
from typing import Protocol

from sqlalchemy.orm import Session

from services.composition.context import MemoComposeContext
from services.composition.schemas import ComposedMemoProse


class CompositionError(Exception):
    """Raised when a provider can't produce a validated, numeral-traceable
    ComposedMemoProse — a malformed LLM response, a missing fixture, a
    misconfigured key, or prose containing an untraceable numeral.
    Composition fails closed: a route never falls back to inventing
    prose."""


class CompositionProvider(Protocol):
    """P-COMPOSE's interface — see ai/prompts/P-COMPOSE.v1.md for the
    system rule this implements, and
    services/composition/fixture_provider.py /
    anthropic_provider.py for the two implementations."""

    def compose(
        self,
        context: MemoComposeContext,
        *,
        session: Session | None = None,
        tenant_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> ComposedMemoProse: ...
