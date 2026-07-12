"""F10's metrics pipeline: every board metric is a MetricsEvent row,
following the exact pattern services/onboarding_metrics.py established
for F3 — an event_name constant, a JSONB properties payload, called from
the state transition that completes the thing being measured, not from
a separate "compute metrics" pass. See services/metrics_report.py for
the monthly aggregation that reads these back without manual collation.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from db.models import MemoVersion, MetricsEvent

REVIEW_COMPLETED_EVENT = "memo.review_completed"
ASSUMPTION_OVERRIDDEN_EVENT = "memo.assumption_overridden"
EXPOSURE_LIST_GENERATED_EVENT = "analysis.exposure_list_generated"
MEMO_APPROVED_EVENT = "memo.approved"


def record_review_minutes(
    session: Session, *, memo_version: MemoVersion, reviewer_user_id: uuid.UUID
) -> MetricsEvent | None:
    """Automatic F7 board metric: minutes between a memo version entering
    review (submitted_at) and being approved (approved_at) — no separate
    timer, no manual entry. A no-op if either timestamp is missing (a
    memo can only reach here via submit_for_review -> approve_memo, both
    of which always set their timestamp, but this stays defensive rather
    than assuming the caller's invariant holds)."""
    if memo_version.submitted_at is None or memo_version.approved_at is None:
        return None
    minutes = (memo_version.approved_at - memo_version.submitted_at).total_seconds() / 60
    event = MetricsEvent(
        tenant_id=memo_version.tenant_id,
        workspace_id=memo_version.workspace_id,
        event_name=REVIEW_COMPLETED_EVENT,
        properties={
            "memo_version_id": str(memo_version.id),
            "reviewer_user_id": str(reviewer_user_id),
            "review_minutes": round(minutes, 2),
            "submitted_at": memo_version.submitted_at.isoformat(),
            "approved_at": memo_version.approved_at.isoformat(),
        },
    )
    session.add(event)
    session.flush()
    return event


def record_assumption_override(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    memo_version_id: uuid.UUID,
    assumption_key: str,
) -> MetricsEvent:
    """F10's override-count metric — one event per override, so a count
    is just `SELECT count(*) ... WHERE event_name = ...`."""
    event = MetricsEvent(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        event_name=ASSUMPTION_OVERRIDDEN_EVENT,
        properties={"memo_version_id": str(memo_version_id), "assumption_key": assumption_key},
    )
    session.add(event)
    session.flush()
    return event


def record_exposure_list_generated(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    entity_profile_id: uuid.UUID,
    entity_profile_created_at: datetime,
    generated_at: datetime,
) -> MetricsEvent:
    """F10's time-to-exposure-list metric: minutes from an entity
    profile's first version to its first completed analysis."""
    minutes = (generated_at - entity_profile_created_at).total_seconds() / 60
    event = MetricsEvent(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        event_name=EXPOSURE_LIST_GENERATED_EVENT,
        properties={
            "entity_profile_id": str(entity_profile_id),
            "time_to_exposure_list_minutes": round(minutes, 2),
        },
    )
    session.add(event)
    session.flush()
    return event


def record_memo_approved(
    session: Session, *, memo_version: MemoVersion, memo_created_at: datetime
) -> MetricsEvent:
    """F10's time-to-approved-memo metric: minutes from the memo (its
    first version) being created to this version's approval."""
    approved_at = memo_version.approved_at
    minutes = (
        (approved_at - memo_created_at).total_seconds() / 60 if approved_at is not None else None
    )
    event = MetricsEvent(
        tenant_id=memo_version.tenant_id,
        workspace_id=memo_version.workspace_id,
        event_name=MEMO_APPROVED_EVENT,
        properties={
            "memo_version_id": str(memo_version.id),
            "time_to_approved_memo_minutes": round(minutes, 2) if minutes is not None else None,
        },
    )
    session.add(event)
    session.flush()
    return event
