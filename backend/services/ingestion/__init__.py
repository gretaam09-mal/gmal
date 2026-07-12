"""Document and data ingestion pipeline: pulls raw sources into storage.

services.instrument_onboarding uses segment_clauses/hash_text from here
to turn a regulatory instrument's raw text into citable Clause rows.
"""

from services.ingestion.segmenter import SegmentedClause, hash_text, segment_clauses

__all__ = ["SegmentedClause", "hash_text", "segment_clauses"]
