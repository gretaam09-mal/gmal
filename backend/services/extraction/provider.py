from typing import Protocol

from services.extraction.schemas import ExtractedObligation


class ExtractionError(Exception):
    """Raised when a provider can't produce a validated ExtractedObligation
    — a malformed LLM response, a missing fixture, or a misconfigured key.
    Extraction fails closed: a route never falls back to inventing a
    obligation to paper over an error."""


class ExtractionProvider(Protocol):
    """P-EXTRACT's interface — see ai/prompts/P-EXTRACT.v1.md for the
    system rule this implements, and services/extraction/fixture_provider.py
    / anthropic_provider.py for the two implementations."""

    def extract(
        self, *, clause_text: str, clause_ref: str, instrument_title: str
    ) -> ExtractedObligation: ...
