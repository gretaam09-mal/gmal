"""Splits raw instrument text into individually-citable clauses.

Citations must always point at a clause, never a whole instrument — this
is what makes that possible. Pure text processing, no I/O; the DB
orchestration that persists the result lives in
services/instrument_onboarding.py.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

# A clause boundary is a blank-line-separated paragraph whose first line
# starts with a numbered heading like "1." or "12A." — the number becomes
# the clause_ref ("s.1", "s.12A"). A paragraph without one still becomes
# its own clause (clause_ref "cl.<n>", sequential) rather than being
# dropped or merged — every sentence of the source text ends up citable.
_CLAUSE_HEADER = re.compile(r"^(?P<ref>\d+[A-Za-z]?)\.\s+")


@dataclass(frozen=True)
class SegmentedClause:
    clause_ref: str
    text: str
    ordinal: int


def hash_text(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def segment_clauses(raw_text: str) -> list[SegmentedClause]:
    paragraphs = [p.strip() for p in raw_text.strip().split("\n\n") if p.strip()]
    clauses: list[SegmentedClause] = []
    for ordinal, paragraph in enumerate(paragraphs, start=1):
        match = _CLAUSE_HEADER.match(paragraph)
        if match:
            clause_ref = f"s.{match.group('ref')}"
            text = paragraph[match.end() :].strip()
        else:
            clause_ref = f"cl.{ordinal}"
            text = paragraph
        clauses.append(SegmentedClause(clause_ref=clause_ref, text=text, ordinal=ordinal))
    return clauses
