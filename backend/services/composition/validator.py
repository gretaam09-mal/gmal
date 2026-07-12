"""Post-render numeral-traceability validation for P-COMPOSE output.

CONVENTIONS.md rule 1: "the LLM never computes a number... any AI-written
number must trace to engine output." The provider gives the model
engine-computed figures pre-formatted in the prompt and instructs it to
reuse them verbatim, never compute or reformat a new one; this is the
backstop that actually enforces it, by walking the rendered prose for
anything that looks like a monetary or percentage figure and rejecting
the whole memo if it doesn't match one of the figures the model was
given.

Deliberately narrow: only tokens with a currency symbol, a decimal
point, a thousands-separator comma, or a trailing '%' are treated as
"numerals" here — bare small integers (clause numbers like "3(2)", years
like "2027") are left alone, since those are citations/dates, not
computed figures, and flagging them would make every legitimate clause
reference a false positive.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from services.prose_numerals import extract_numerals, normalise_numeral

if TYPE_CHECKING:
    from services.composition.context import MemoComposeContext
    from services.composition.schemas import ComposedMemoProse

__all__ = [
    "NumeralTraceabilityError",
    "assert_numerals_trace_to_engine_output",
    "extract_numerals",
    "validate_composed_memo",
]


class NumeralTraceabilityError(Exception):
    """Raised when rendered prose contains a numeral that doesn't match
    any of the allowed engine-produced values."""


def assert_numerals_trace_to_engine_output(text: str, allowed_values: frozenset[Decimal]) -> None:
    for token in extract_numerals(text):
        value = normalise_numeral(token)
        if value is None:
            continue
        if value not in allowed_values:
            raise NumeralTraceabilityError(
                f"prose contains numeral {token!r} that doesn't trace to any engine-produced value"
            )


def validate_composed_memo(prose: ComposedMemoProse, context: MemoComposeContext) -> None:
    """Checks every prose field P-COMPOSE produced against the context's
    allowed values — raises on the first untraceable numeral found."""
    allowed = context.allowed_numeral_values()
    texts = [prose.headline_summary, prose.excluded_summary] + [
        f"{obligation.what_it_requires} {obligation.why_it_applies}"
        for obligation in prose.obligations
    ]
    for text in texts:
        assert_numerals_trace_to_engine_output(text, allowed)
