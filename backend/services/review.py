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
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import CostTemplate, Memo, MemoVersion, Obligation, ReviewCorrection
from db.models.enums import MemoStatus
from services.instrument_onboarding import attach_cost_template, correct_obligation

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


# --- Corrections: persist back to the instrument/template layer -------------


def record_obligation_correction(
    session: Session,
    *,
    memo_version: MemoVersion,
    obligation: Obligation,
    summary: str,
    obligation_type: str,
    fields: dict[str, Any],
    confidence: int,
    corrected_by_user_id: uuid.UUID,
    note: str,
) -> tuple[Obligation, ReviewCorrection]:
    """A reviewer's fix to an obligation, made while reviewing a memo.

    services/instrument_onboarding.py::correct_obligation does the actual
    bitemporal versioning (closes the old row, inserts a fresh unapproved
    one) — this only additionally records that this particular review is
    why it happened, so the *next* memo built against this instrument
    benefits from the fix too, not just this one (F7's whole point).
    """
    corrected = correct_obligation(
        session,
        obligation=obligation,
        summary=summary,
        obligation_type=obligation_type,
        fields=fields,
        confidence=confidence,
    )
    correction = ReviewCorrection(
        tenant_id=memo_version.tenant_id,
        workspace_id=memo_version.workspace_id,
        memo_version_id=memo_version.id,
        obligation_id=corrected.id,
        corrected_by_user_id=corrected_by_user_id,
        note=note,
    )
    session.add(correction)
    session.flush()
    return corrected, correction


def record_cost_template_correction(
    session: Session,
    *,
    memo_version: MemoVersion,
    obligation: Obligation,
    name: str,
    drivers: list[dict[str, Any]],
    formula: dict[str, Any],
    currency: str,
    source_basis: str,
    maturity_tier: str,
    corrected_by_user_id: uuid.UUID,
    note: str,
    first_obligation_date: date | None = None,
    transition_months: int = 0,
) -> tuple[CostTemplate, ReviewCorrection]:
    """As record_obligation_correction, for a reviewer's fix to a cost
    template — attach_cost_template already always versions (cost
    templates have no draft state), so this only adds the provenance
    record linking it back to the review that triggered it."""
    corrected = attach_cost_template(
        session,
        obligation=obligation,
        name=name,
        drivers=drivers,
        formula=formula,
        currency=currency,
        source_basis=source_basis,
        maturity_tier=maturity_tier,
        first_obligation_date=first_obligation_date,
        transition_months=transition_months,
    )
    correction = ReviewCorrection(
        tenant_id=memo_version.tenant_id,
        workspace_id=memo_version.workspace_id,
        memo_version_id=memo_version.id,
        cost_template_id=corrected.id,
        corrected_by_user_id=corrected_by_user_id,
        note=note,
    )
    session.add(correction)
    session.flush()
    return corrected, correction
