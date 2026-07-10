from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ImpactResult:
    """A single quantified figure produced by the engine, never by an LLM."""

    line_item_id: str
    amount: Decimal
    currency: str = "GBP"
