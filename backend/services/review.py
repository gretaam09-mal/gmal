"""F7 orchestration: the reviewer queue, corrections that persist back to
the instrument/template layer, and the automatic review-minutes metric.

The queue's *ordering* is a pure function (sort_review_queue) — it does
no I/O and is fully unit-tested on its own; list_review_queue is the
thin DB-touching half that assembles ReviewQueueEntry rows and hands
them to it.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Memo, MemoVersion
from db.models.enums import MemoStatus

_GRADE_URGENCY = {"A": 0, "B": 1, "C": 2, "D": 3}
_MISSING_GRADE_URGENCY = 4  # worse than a "D" — an ungraded memo is the most urgent unknown


@dataclass(frozen=True)
class ReviewQueueEntry:
    memo_id: uuid.UUID
    memo_title: str
    version_id: uuid.UUID
    version_number: int
    status: MemoStatus
    confidence_grade: str | None
    ambiguous_count: int
    submitted_at: datetime | None
    created_at: datetime


def _urgency(entry: ReviewQueueEntry) -> int:
    return _GRADE_URGENCY.get(entry.confidence_grade or "", _MISSING_GRADE_URGENCY)


def sort_review_queue(entries: list[ReviewQueueEntry]) -> list[ReviewQueueEntry]:
    """Low-confidence extractions and ambiguous applicability calls
    pre-flagged at the top: worst confidence grade first, then most
    ambiguous items, then oldest submission (FIFO) as a tiebreaker."""
    return sorted(
        entries,
        key=lambda e: (-_urgency(e), -e.ambiguous_count, e.submitted_at or e.created_at),
    )


def _ambiguous_count(content: dict) -> int:
    return sum(1 for item in content.get("excluded", []) if item.get("outcome") == "ambiguous")


def list_review_queue(session: Session, workspace_id: uuid.UUID) -> list[ReviewQueueEntry]:
    rows = session.execute(
        select(MemoVersion, Memo)
        .join(Memo, Memo.id == MemoVersion.memo_id)
        .where(
            Memo.workspace_id == workspace_id,
            MemoVersion.status.in_((MemoStatus.DRAFT, MemoStatus.IN_REVIEW)),
        )
    ).all()
    entries = [
        ReviewQueueEntry(
            memo_id=memo.id,
            memo_title=memo.title,
            version_id=version.id,
            version_number=version.version,
            status=version.status,
            confidence_grade=version.confidence_grade,
            ambiguous_count=_ambiguous_count(version.content),
            submitted_at=version.submitted_at,
            created_at=version.created_at,
        )
        for version, memo in rows
    ]
    return sort_review_queue(entries)
