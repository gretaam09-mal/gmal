"""Structured extraction from ingested documents (LLM-assisted, non-arithmetic).

See ai/prompts/P-EXTRACT.v1.md for the prompt this implements.
"""

from services.extraction.fixture_provider import FixtureExtractionProvider
from services.extraction.provider import ExtractionError, ExtractionProvider
from services.extraction.schemas import ExtractedField, ExtractedObligation

__all__ = [
    "ExtractedField",
    "ExtractedObligation",
    "ExtractionError",
    "ExtractionProvider",
    "FixtureExtractionProvider",
]
