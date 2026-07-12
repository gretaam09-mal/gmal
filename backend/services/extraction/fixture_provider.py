"""A deterministic, offline stand-in for P-EXTRACT.

Used by tests, the golden-set runner, and scripts/populate_sample_
instruments.py — no test in this repo makes a live model call, matching
the fixture-testing pattern services/companies_house established. A
route only ever gets this via explicit dependency injection, never as a
silent fallback when a real key is missing (see api/deps.py — the
default provider is AnthropicExtractionProvider, which fails closed).
"""

from __future__ import annotations

from services.extraction.provider import ExtractionError
from services.extraction.schemas import ExtractedObligation


class FixtureExtractionProvider:
    def __init__(self, fixtures: dict[str, ExtractedObligation] | None = None) -> None:
        self._fixtures: dict[str, ExtractedObligation] = dict(fixtures or {})

    def register(self, clause_ref: str, obligation: ExtractedObligation) -> None:
        self._fixtures[clause_ref] = obligation

    def extract(
        self, *, clause_text: str, clause_ref: str, instrument_title: str
    ) -> ExtractedObligation:
        del clause_text, instrument_title  # deterministic on clause_ref only
        try:
            return self._fixtures[clause_ref]
        except KeyError:
            raise ExtractionError(
                f"No fixture registered for clause {clause_ref!r} — "
                "FixtureExtractionProvider.register() it first"
            ) from None
