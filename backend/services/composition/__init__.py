"""P-COMPOSE: turns engine output plus approved rationale metadata and
clause texts into memo prose — see ai/prompts/P-COMPOSE.v1.md. Numbers
never come from the LLM; see validator.py for the post-render check.
"""

from services.composition.anthropic_provider import AnthropicCompositionProvider
from services.composition.context import MemoComposeContext, ObligationComposeInput
from services.composition.fixture_provider import FixtureCompositionProvider
from services.composition.provider import CompositionError, CompositionProvider
from services.composition.schemas import ComposedMemoProse, ComposedObligationProse

__all__ = [
    "AnthropicCompositionProvider",
    "CompositionError",
    "CompositionProvider",
    "ComposedMemoProse",
    "ComposedObligationProse",
    "FixtureCompositionProvider",
    "MemoComposeContext",
    "ObligationComposeInput",
]
