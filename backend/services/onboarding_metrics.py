"""Captures onboarding hours per instrument automatically — a board
metric (how long it takes to bring one piece of regulation from raw text
to a fully-reviewed, ready-to-evaluate set of obligations).

No separate "start the clock" action is needed: an Instrument's own
`recorded_at` (set the moment its text is ingested — see
services/instrument_onboarding.py::ingest_instrument) is the start; the
moment its last obligation is approved is the end. Called from
approve_obligation after every approval — a no-op until the instrument
is actually fully approved, and a no-op again after that (idempotent,
never double-recorded).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Clause, Instrument, InstrumentVersion, MetricsEvent, Obligation

ONBOARDING_COMPLETED_EVENT = "instrument.onboarding_completed"


def is_instrument_fully_approved(session: Session, instrument_id: uuid.UUID) -> bool:
    """True once every *current* obligation (valid_to IS NULL — the latest
    version of each) derived from this instrument is approved, and there
    is at least one. An instrument with zero obligations yet isn't
    "onboarded", it just hasn't started."""
    current_obligations = session.execute(
        select(Obligation.approved)
        .join(Clause, Clause.id == Obligation.clause_id)
        .join(InstrumentVersion, InstrumentVersion.id == Clause.instrument_version_id)
        .where(
            InstrumentVersion.instrument_id == instrument_id,
            Obligation.valid_to.is_(None),
        )
    ).scalars().all()
    return bool(current_obligations) and all(current_obligations)


def _already_recorded(session: Session, instrument_id: uuid.UUID) -> bool:
    existing = session.execute(
        select(MetricsEvent.id).where(
            MetricsEvent.event_name == ONBOARDING_COMPLETED_EVENT,
            MetricsEvent.properties.contains({"instrument_id": str(instrument_id)}),
        )
    ).first()
    return existing is not None


def maybe_record_onboarding_completion(
    session: Session, instrument: Instrument
) -> MetricsEvent | None:
    if not is_instrument_fully_approved(session, instrument.id):
        return None
    if _already_recorded(session, instrument.id):
        return None

    completed_at = datetime.now(UTC)
    started_at = instrument.recorded_at
    hours = (completed_at - started_at).total_seconds() / 3600

    event = MetricsEvent(
        event_name=ONBOARDING_COMPLETED_EVENT,
        properties={
            "instrument_id": str(instrument.id),
            "instrument_title": instrument.title,
            "onboarding_hours": round(hours, 2),
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
        },
    )
    session.add(event)
    session.flush()
    return event
